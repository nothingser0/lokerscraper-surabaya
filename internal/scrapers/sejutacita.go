package scrapers

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"

	"lokerscraper-surabaya/internal/config"
	"lokerscraper-surabaya/internal/model"
	"lokerscraper-surabaya/internal/utils"
)

type SejutaCitaScraper struct {
	*BaseClient
	cfg *config.Config
}

func NewSejutaCitaScraper(cfg *config.Config) *SejutaCitaScraper {
	return &SejutaCitaScraper{
		BaseClient: NewBaseClient(12*time.Second, 0),
		cfg:        cfg,
	}
}

func (s *SejutaCitaScraper) SourceName() string {
	return "SejutaCita"
}

func (s *SejutaCitaScraper) SetSeenIDs(seen map[string]bool) {
	s.SeenIDs = seen
}

func (s *SejutaCitaScraper) FetchJobs() ([]model.Job, error) {
	var scrapedJobs []model.Job
	seenJobIDs := make(map[string]bool)
	defaultLoc := "Surabaya"
	if len(s.cfg.Locations) > 0 {
		defaultLoc = s.cfg.Locations[0]
	}

	for _, kw := range s.cfg.Keywords {
		apiURL := fmt.Sprintf("https://api.sejutacita.id/v1/explore-job/job?cityIds%%5B0%%5D=265&published=true&limit=20&q=%s",
			url.QueryEscape(kw))

		req, err := http.NewRequest("GET", apiURL, nil)
		if err != nil {
			continue
		}
		req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
		req.Header.Set("Accept", "application/json")

		resp, err := s.DoRequest(req)
		if err != nil {
			log.Printf("[SejutaCita] Request error for keyword %s: %v", kw, err)
			continue
		}
		if resp.StatusCode != 200 {
			resp.Body.Close()
			continue
		}

		body, err := ReadBody(resp)
		if err != nil {
			continue
		}

		var parsed map[string]interface{}
		if err := json.Unmarshal(body, &parsed); err != nil {
			continue
		}

		var jobsData []interface{}
		if dataObj, ok := parsed["data"].(map[string]interface{}); ok {
			if docs, ok := dataObj["docs"].([]interface{}); ok {
				jobsData = docs
			}
		} else if dataList, ok := parsed["data"].([]interface{}); ok {
			jobsData = dataList
		}

		for _, item := range jobsData {
			job, ok := item.(map[string]interface{})
			if !ok {
				continue
			}

			rawID := fmt.Sprintf("%v", job["id"])
			if rawID == "" || rawID == "<nil>" {
				rawID = fmt.Sprintf("%v", job["_id"])
			}
			if rawID == "" || rawID == "<nil>" || seenJobIDs[rawID] {
				continue
			}

			title, _ := job["role"].(string)
			if title == "" {
				title, _ = job["title"].(string)
			}
			if title == "" {
				title = "Untitled"
			}

			companyName := "Unknown"
			var logoURL *string
			var companyIndustry *string
			var benefitsData []interface{}
			if companyData, ok := job["company"].(map[string]interface{}); ok {
				if cname, ok := companyData["name"].(string); ok && cname != "" {
					companyName = cname
				}
				if logo, ok := companyData["logoUrl"].(string); ok && logo != "" {
					logoURL = &logo
				}
				if sector, ok := companyData["sector"].(string); ok && sector != "" {
					companyIndustry = &sector
				}
				if insightObj, ok := companyData["insight"].(map[string]interface{}); ok {
					if b, ok := insightObj["benefits"].([]interface{}); ok {
						benefitsData = b
					}
				}
			}

			var locParts []string
			if cityData, ok := job["city"].(map[string]interface{}); ok {
				if cname, ok := cityData["name"].(string); ok && cname != "" {
					locParts = append(locParts, cname)
				}
			}
			if countryData, ok := job["country"].(map[string]interface{}); ok {
				if cname, ok := countryData["name"].(string); ok && cname != "" {
					locParts = append(locParts, cname)
				}
			}
			locationStr := defaultLoc
			if len(locParts) > 0 {
				locationStr = strings.Join(locParts, ", ")
			}

			var salMin, salMax *int
			if salRange, ok := job["salaryRange"].(map[string]interface{}); ok {
				if s, ok := salRange["start"].(float64); ok && s > 0 {
					is := int(s)
					salMin = &is
				} else if s, ok := salRange["min"].(float64); ok && s > 0 {
					is := int(s)
					salMin = &is
				}
				if e, ok := salRange["end"].(float64); ok && e > 0 {
					ie := int(e)
					salMax = &ie
				} else if e, ok := salRange["max"].(float64); ok && e > 0 {
					ie := int(e)
					salMax = &ie
				}
			}
			var salCurr *string
			if salMin != nil || salMax != nil {
				c := "IDR"
				salCurr = &c
			}

			workplaceType := strings.ToLower(fmt.Sprintf("%v", job["workplaceType"]))
			workMode := "On-site"
			if strings.Contains(workplaceType, "remote") {
				workMode = "Remote"
			} else if strings.Contains(workplaceType, "hybrid") {
				workMode = "Hybrid"
			}

			slug, _ := job["slug"].(string)
			if slug == "" {
				slug = rawID
			}
			jobURL := fmt.Sprintf("https://sejutacita.id/job/%s", slug)

			publishedAt, _ := job["publishedAt"].(string)
			if publishedAt == "" {
				publishedAt, _ = job["createdAt"].(string)
			}
			postedAt := time.Now().UTC().Format("2006-01-02")
			if len(publishedAt) >= 10 {
				postedAt = publishedAt[:10]
			}

			var appDeadline *string
			if dl, ok := job["lastActivelyHiringAt"].(string); ok && len(dl) >= 10 {
				d := dl[:10]
				appDeadline = &d
			}

			rawType := "Full-time"
			if empTypes, ok := job["employmentTypes"].([]interface{}); ok && len(empTypes) > 0 {
				rawType = fmt.Sprintf("%v", empTypes[0])
			} else if et, ok := job["employmentType"].(string); ok && et != "" {
				rawType = et
			}
			workType := utils.FormatJobType(rawType)

			var applicantCount *int
			if stats, ok := job["stats"].(map[string]interface{}); ok {
				if ac, ok := stats["applicantCount"].(float64); ok {
					iac := int(ac)
					applicantCount = &iac
				}
			}

			var openings *int
			if op, ok := job["applicantPrioritySlots"].(float64); ok && op > 0 {
				iop := int(op)
				openings = &iop
			}

			var skillsList []string
			if rawSkills, ok := job["skills"].([]interface{}); ok {
				for _, sk := range rawSkills {
					if skMap, ok := sk.(map[string]interface{}); ok {
						if name, ok := skMap["name"].(string); ok && name != "" {
							skillsList = append(skillsList, name)
						}
					}
				}
			}

			var qualifications *string
			if candPref, ok := job["candidatePreference"].(map[string]interface{}); ok {
				var qualParts []string
				if m, ok := candPref["major"].(string); ok && m != "" {
					qualParts = append(qualParts, fmt.Sprintf("Major: %s", m))
				}
				if u, ok := candPref["university"].(string); ok && u != "" {
					qualParts = append(qualParts, fmt.Sprintf("University: %s", u))
				}
				if g, ok := candPref["minimumGpa"].(float64); ok && g > 0 {
					qualParts = append(qualParts, fmt.Sprintf("Min GPA: %.2f", g))
				}
				if len(qualParts) > 0 {
					q := strings.Join(qualParts, "; ")
					qualifications = &q
				}
			}

			var benefits []string
			for _, b := range benefitsData {
				if dec := utils.DecodeBenefit(b); dec != nil {
					benefits = append(benefits, *dec)
				}
			}

			scrapedJobs = append(scrapedJobs, model.Job{
				RawID:               rawID,
				Source:              s.SourceName(),
				Title:               utils.SanitizeText(title),
				Company:             utils.SanitizeText(companyName),
				LogoURL:             logoURL,
				CompanyIndustry:     companyIndustry,
				Location:            utils.SanitizeText(locationStr),
				SalaryMin:           salMin,
				SalaryMax:           salMax,
				SalaryCurrency:      salCurr,
				WorkType:            &workType,
				WorkMode:            workMode,
				PostedAt:            postedAt,
				ApplicationDeadline: appDeadline,
				ApplicantCount:      applicantCount,
				NumberOfOpenings:    openings,
				Skills:              skillsList,
				Qualifications:      qualifications,
				Benefits:            benefits,
				URL:                 jobURL,
				ScrapedAt:           time.Now().UTC().Format(time.RFC3339),
			})

			seenJobIDs[rawID] = true
		}
	}

	return scrapedJobs, nil
}
