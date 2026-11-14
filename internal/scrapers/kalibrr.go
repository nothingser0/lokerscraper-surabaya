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

type KalibrrScraper struct {
	*BaseClient
	cfg *config.Config
}

func NewKalibrrScraper(cfg *config.Config) *KalibrrScraper {
	return &KalibrrScraper{
		BaseClient: NewBaseClient(12*time.Second, 0),
		cfg:        cfg,
	}
}

func (s *KalibrrScraper) SourceName() string {
	return "Kalibrr"
}

func (s *KalibrrScraper) SetSeenIDs(seen map[string]bool) {
	s.SeenIDs = seen
}

func (s *KalibrrScraper) FetchJobs() ([]model.Job, error) {
	var scrapedJobs []model.Job
	seenJobIDs := make(map[string]bool)
	defaultLoc := "Surabaya"
	if len(s.cfg.Locations) > 0 {
		defaultLoc = s.cfg.Locations[0]
	}

	for _, kw := range s.cfg.Keywords {
		apiURL := fmt.Sprintf("https://www.kalibrr.com/kjs/job_board/search?keyword=%s&location=%s&limit=20&offset=0",
			url.QueryEscape(kw), url.QueryEscape(defaultLoc))

		req, err := http.NewRequest("GET", apiURL, nil)
		if err != nil {
			continue
		}
		req.Header.Set("User-Agent", DefaultUserAgent)
		req.Header.Set("Accept", "application/json, text/plain, */*")

		resp, err := s.DoRequest(req)
		if err != nil {
			log.Printf("[Kalibrr] Request error for keyword %s: %v", kw, err)
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

		jobsData, _ := parsed["jobs"].([]interface{})
		for _, item := range jobsData {
			job, ok := item.(map[string]interface{})
			if !ok {
				continue
			}

			rawID := fmt.Sprintf("%v", job["id"])
			if rawID == "" || seenJobIDs[rawID] {
				continue
			}

			locationStr := defaultLoc
			if googleLoc, ok := job["google_location"].(map[string]interface{}); ok {
				if addrComp, ok := googleLoc["address_components"].(map[string]interface{}); ok {
					if city, ok := addrComp["city"].(string); ok && city != "" {
						locationStr = city
					}
				}
			}

			locLower := strings.ToLower(locationStr)
			jobName, _ := job["name"].(string)
			jobNameLower := strings.ToLower(jobName)
			matchLoc := false
			for _, l := range s.cfg.Locations {
				if strings.Contains(locLower, l) || strings.Contains(jobNameLower, l) {
					matchLoc = true
					break
				}
			}
			if !matchLoc {
				continue
			}

			companyName := "Unknown"
			if cname, ok := job["company_name"].(string); ok && cname != "" {
				companyName = cname
			}

			companyInfo, _ := job["company_info"].(map[string]interface{})
			companyCode := "company"
			if c, ok := job["company_code"].(string); ok && c != "" {
				companyCode = c
			} else if companyInfo != nil {
				if c, ok := companyInfo["code"].(string); ok && c != "" {
					companyCode = c
				}
			}

			var logoURL *string
			var companyIndustry *string
			var companyDesc *string
			if companyInfo != nil {
				if logo, ok := companyInfo["logo"].(string); ok && logo != "" {
					logoURL = &logo
				} else if logo, ok := companyInfo["logo_small"].(string); ok && logo != "" {
					logoURL = &logo
				}
				if ind, ok := companyInfo["industry"].(string); ok && ind != "" {
					companyIndustry = &ind
				}
				if desc, ok := companyInfo["description"].(string); ok && desc != "" {
					companyDesc = &desc
				}
			}

			slug, _ := job["slug"].(string)
			if slug == "" {
				slug = rawID
			}
			jobURL := fmt.Sprintf("https://www.kalibrr.com/c/%s/jobs/%s/%s", companyCode, rawID, slug)

			tenure, _ := job["tenure"].(string)
			if tenure == "" {
				tenure = "Full-time"
			}
			jobType := utils.FormatJobType(tenure)

			createdAt, _ := job["created_at"].(string)
			postedAt := time.Now().UTC().Format("2006-01-02")
			if len(createdAt) >= 10 {
				postedAt = createdAt[:10]
			}

			endDate, _ := job["application_end_date"].(string)
			var appDeadline *string
			if len(endDate) >= 10 {
				d := endDate[:10]
				appDeadline = &d
			}

			var salMin, salMax *int
			if bSal, ok := job["base_salary"].(float64); ok && bSal > 0 {
				im := int(bSal)
				salMin = &im
			}
			if mSal, ok := job["maximum_salary"].(float64); ok && mSal > 0 {
				im := int(mSal)
				salMax = &im
			}
			var salCurr *string
			if curr, ok := job["salary_currency"].(string); ok && curr != "" {
				salCurr = &curr
			} else if salMin != nil || salMax != nil {
				c := "IDR"
				salCurr = &c
			}

			var openings *int
			if op, ok := job["number_of_openings"].(float64); ok && op > 0 {
				iop := int(op)
				openings = &iop
			}

			var skillsList []string
			if sdsSkills, ok := job["job_sds_skills"].([]interface{}); ok {
				for _, sk := range sdsSkills {
					if skMap, ok := sk.(map[string]interface{}); ok {
						if sdsObj, ok := skMap["sds_skill"].(map[string]interface{}); ok {
							if sname, ok := sdsObj["name"].(string); ok && sname != "" {
								skillsList = append(skillsList, sname)
							}
						}
					}
				}
			}

			experience := utils.DecodeKalibrrExperience(job["work_experience"])
			education := utils.DecodeKalibrrEducation(job["education_level"])

			rawDesc, _ := job["description"].(string)
			var jobDesc *string
			if cl := utils.CleanDescription(rawDesc); cl != "" {
				jobDesc = &cl
			}

			rawQual, _ := job["qualifications"].(string)
			var qualifications *string
			if cl := utils.CleanDescription(rawQual); cl != "" {
				qualifications = &cl
			}

			var benefits []string
			if perks, ok := job["perks"].(map[string]interface{}); ok {
				if types, ok := perks["types"].([]interface{}); ok {
					for _, p := range types {
						if dec := utils.DecodeBenefit(p); dec != nil {
							benefits = append(benefits, *dec)
						}
					}
				}
				if other := perks["other"]; other != nil {
					if dec := utils.DecodeBenefit(other); dec != nil {
						benefits = append(benefits, *dec)
					}
				}
			}

			workMode := "On-site"
			if isWfh, _ := job["is_work_from_home"].(bool); isWfh {
				workMode = "Remote"
			} else if isHyb, _ := job["is_hybrid"].(bool); isHyb {
				workMode = "Hybrid"
			}

			scrapedJobs = append(scrapedJobs, model.Job{
				RawID:               rawID,
				Source:              s.SourceName(),
				Title:               utils.SanitizeText(jobName),
				Company:             utils.SanitizeText(companyName),
				LogoURL:             logoURL,
				CompanyIndustry:     companyIndustry,
				CompanyDescription:  companyDesc,
				Location:            utils.SanitizeText(locationStr),
				SalaryMin:           salMin,
				SalaryMax:           salMax,
				SalaryCurrency:      salCurr,
				WorkType:            &jobType,
				WorkMode:            workMode,
				PostedAt:            postedAt,
				ApplicationDeadline: appDeadline,
				NumberOfOpenings:    openings,
				Skills:              skillsList,
				Experience:          experience,
				Education:           education,
				JobDescription:      jobDesc,
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
