package scrapers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"strings"
	"time"

	"lokerscraper-surabaya/internal/config"
	"lokerscraper-surabaya/internal/model"
	"lokerscraper-surabaya/internal/utils"
)

var glintsLocationIDs = map[string]string{
	"surabaya":   "0822446a-8784-4af4-bc88-9f9294fca382",
	"sidoarjo":   "0c51be85-7a6e-4fe6-b802-4bbec5d5dcda",
	"gresik":     "1c0b4d54-562a-466a-a9d6-c609ac2eb4c3",
	"jawa timur": "bc26ec98-d599-44cb-84e7-c92f6d87e102",
}

const glintsSearchQuery = `query searchJobs($data: JobSearchConditionInput!) {
  searchJobs(data: $data) {
    jobsInPage {
      id
      title
      workArrangementOption
      type
      createdAt
      updatedAt
      minYearsOfExperience
      maxYearsOfExperience
      educationLevel
      isRemote
      company {
        name
        logo
        industry {
          name
        }
      }
      location {
        name
        formattedName
        parents {
          name
          formattedName
          level
        }
      }
      salaries {
        CurrencyCode
        minAmount
        maxAmount
      }
      skills {
        skill {
          name
        }
      }
    }
  }
}`

type GlintsScraper struct {
	*BaseClient
	cfg *config.Config
}

func NewGlintsScraper(cfg *config.Config) *GlintsScraper {
	return &GlintsScraper{
		BaseClient: NewBaseClient(15*time.Second, 300*time.Millisecond),
		cfg:        cfg,
	}
}

func (s *GlintsScraper) SourceName() string {
	return "Glints"
}

func (s *GlintsScraper) SetSeenIDs(seen map[string]bool) {
	s.SeenIDs = seen
}

func (s *GlintsScraper) matchesKeywords(title string) bool {
	if len(s.cfg.Keywords) == 0 {
		return true
	}
	titleLower := strings.ToLower(title)
	for _, kw := range s.cfg.Keywords {
		if strings.Contains(titleLower, strings.ToLower(kw)) {
			return true
		}
	}
	return false
}

func (s *GlintsScraper) resolveLocationIDs() []string {
	var ids []string
	seen := make(map[string]bool)
	for _, loc := range s.cfg.Locations {
		if id, ok := glintsLocationIDs[strings.ToLower(strings.TrimSpace(loc))]; ok && !seen[id] {
			seen[id] = true
			ids = append(ids, id)
		}
	}
	if len(ids) == 0 {
		ids = []string{glintsLocationIDs["surabaya"]}
	}
	return ids
}

func (s *GlintsScraper) fetchJobDetail(rawID string) (string, string) {
	apiURL := fmt.Sprintf("https://glints.com/api/jobs/%s", rawID)
	req, err := http.NewRequest("GET", apiURL, nil)
	if err != nil {
		return "", ""
	}
	req.Header.Set("User-Agent", DefaultUserAgent)
	req.Header.Set("Accept", "application/json")
	req.Header.Set("Accept-Language", "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7")
	req.Header.Set("Referer", "https://glints.com/id/opportunities/jobs/explore")

	resp, err := s.DoRequest(req)
	if err != nil {
		s.Client.CloseIdleConnections()
		return "", ""
	}
	if resp.StatusCode != 200 {
		resp.Body.Close()
		return "", ""
	}
	body, err := ReadBody(resp)
	if err != nil {
		return "", ""
	}

	var parsed map[string]interface{}
	if err := json.Unmarshal(body, &parsed); err != nil {
		return "", ""
	}
	data, ok := parsed["data"].(map[string]interface{})
	if !ok {
		return "", ""
	}

	jobDesc := ""
	if descRaw := utils.DraftJSToText(data["descriptionRaw"]); descRaw != nil {
		jobDesc = *descRaw
	}
	return jobDesc, ""
}

func (s *GlintsScraper) queryJobsGraphQL(kw string, locIDs []string) ([]interface{}, error) {
	payload := map[string]interface{}{
		"query": glintsSearchQuery,
		"variables": map[string]interface{}{
			"data": map[string]interface{}{
				"SearchTerm":  kw,
				"CountryCode": "ID",
				"LocationIds": locIDs,
			},
		},
	}
	bodyBytes, err := json.Marshal(payload)
	if err != nil {
		return nil, err
	}

	var lastErr error
	for attempt := 0; attempt < 2; attempt++ {
		if attempt > 0 {
			s.Client.CloseIdleConnections()
			time.Sleep(time.Duration(attempt) * time.Second)
		}

		req, err := http.NewRequest("POST", "https://glints.com/api/v2-alc/graphql", bytes.NewReader(bodyBytes))
		if err != nil {
			return nil, err
		}
		req.Header.Set("User-Agent", DefaultUserAgent)
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Accept", "application/json")
		req.Header.Set("Accept-Language", "id-ID,id;q=0.9,en-US;q=0.8,en;q=0.7")
		req.Header.Set("Origin", "https://glints.com")
		req.Header.Set("Referer", "https://glints.com/id/opportunities/jobs/explore")

		resp, err := s.DoRequest(req)
		if err != nil {
			lastErr = err
			continue
		}

		if resp.StatusCode == 429 || resp.StatusCode >= 500 {
			lastErr = fmt.Errorf("status %d", resp.StatusCode)
			resp.Body.Close()
			continue
		}
		if resp.StatusCode != 200 {
			resp.Body.Close()
			return nil, fmt.Errorf("unexpected status %d", resp.StatusCode)
		}

		respBody, err := ReadBody(resp)
		if err != nil {
			lastErr = err
			continue
		}

		var parsed map[string]interface{}
		if err := json.Unmarshal(respBody, &parsed); err != nil {
			return nil, err
		}
		dataObj, _ := parsed["data"].(map[string]interface{})
		searchObj, _ := dataObj["searchJobs"].(map[string]interface{})
		jobsInPage, _ := searchObj["jobsInPage"].([]interface{})
		return jobsInPage, nil
	}

	s.Client.CloseIdleConnections()
	return nil, lastErr
}

func formatGlintsLocation(locInfo map[string]interface{}, defaultLoc string) string {
	if locInfo == nil {
		return defaultLoc
	}
	var district string
	if name, ok := locInfo["formattedName"].(string); ok && name != "" {
		district = name
	} else if name, ok := locInfo["name"].(string); ok && name != "" {
		district = name
	}

	var city string
	if parents, ok := locInfo["parents"].([]interface{}); ok {
		for _, p := range parents {
			pMap, ok := p.(map[string]interface{})
			if !ok {
				continue
			}
			lvl, _ := pMap["level"].(float64)
			if int(lvl) == 3 {
				if cname, ok := pMap["name"].(string); ok && cname != "" {
					city = cname
					break
				}
			}
		}
	}

	if district != "" && city != "" && !strings.EqualFold(district, city) {
		return fmt.Sprintf("%s, %s", district, city)
	}
	if city != "" {
		return city
	}
	if district != "" {
		return district
	}
	return defaultLoc
}

func (s *GlintsScraper) FetchJobs() ([]model.Job, error) {
	var scrapedJobs []model.Job
	seenJobIDs := make(map[string]bool)
	defaultLoc := "Surabaya"
	if len(s.cfg.Locations) > 0 {
		defaultLoc = s.cfg.Locations[0]
	}
	locIDs := s.resolveLocationIDs()

	for _, kw := range s.cfg.Keywords {
		jobsData, err := s.queryJobsGraphQL(kw, locIDs)
		if err != nil {
			log.Printf("[Glints] Request error for keyword %s: %v", kw, err)
			continue
		}

		for _, item := range jobsData {
			job, ok := item.(map[string]interface{})
			if !ok {
				continue
			}

			rawID := fmt.Sprintf("%v", job["id"])
			if rawID == "" || seenJobIDs[rawID] {
				continue
			}

			title, _ := job["title"].(string)
			if title == "" {
				title = "Untitled"
			}

			companyName := "Unknown"
			var logoURL *string
			var companyIndustry *string
			if companyInfo, ok := job["company"].(map[string]interface{}); ok {
				if name, ok := companyInfo["name"].(string); ok && name != "" {
					companyName = name
				}
				if logo, ok := companyInfo["logo"].(string); ok && logo != "" {
					if !strings.HasPrefix(logo, "http") {
						logo = "https://images.glints.com/unsafe/glints-dashboard.s3.amazonaws.com/company-logo/" + logo
					}
					logoURL = &logo
				}
				if indObj, ok := companyInfo["industry"].(map[string]interface{}); ok {
					if ind, ok := indObj["name"].(string); ok && ind != "" {
						companyIndustry = &ind
					}
				} else if ind, ok := companyInfo["industry"].(string); ok && ind != "" {
					companyIndustry = &ind
				}
			}

			locInfo, _ := job["location"].(map[string]interface{})
			locationStr := formatGlintsLocation(locInfo, defaultLoc)

			var salMin, salMax *int
			var salCurr *string
			if salariesList, ok := job["salaries"].([]interface{}); ok && len(salariesList) > 0 {
				if firstSal, ok := salariesList[0].(map[string]interface{}); ok {
					if minV, ok := firstSal["minAmount"].(float64); ok && minV > 0 {
						im := int(minV)
						salMin = &im
					}
					if maxV, ok := firstSal["maxAmount"].(float64); ok && maxV > 0 {
						im := int(maxV)
						salMax = &im
					}
					if curr, ok := firstSal["CurrencyCode"].(string); ok && curr != "" {
						salCurr = &curr
					}
				}
			}

			arrangement := strings.ToUpper(fmt.Sprintf("%v", job["workArrangementOption"]))
			isRemote, _ := job["isRemote"].(bool)
			workMode := "On-site"
			if strings.Contains(arrangement, "REMOTE") || isRemote {
				workMode = "Remote"
			} else if strings.Contains(arrangement, "HYBRID") {
				workMode = "Hybrid"
			}

			createdAt, _ := job["createdAt"].(string)
			if createdAt == "" {
				createdAt, _ = job["updatedAt"].(string)
			}
			postedAt := time.Now().UTC().Format("2006-01-02")
			if len(createdAt) >= 10 {
				postedAt = createdAt[:10]
			}

			jobType := utils.FormatJobType(fmt.Sprintf("%v", job["type"]))

			var skillsList []string
			if rawSkills, ok := job["skills"].([]interface{}); ok {
				for _, sk := range rawSkills {
					if skMap, ok := sk.(map[string]interface{}); ok {
						if innerSkill, ok := skMap["skill"].(map[string]interface{}); ok {
							if name, ok := innerSkill["name"].(string); ok && name != "" {
								skillsList = append(skillsList, name)
							}
						} else if name, ok := skMap["name"].(string); ok && name != "" {
							skillsList = append(skillsList, name)
						}
					}
				}
			}

			var experience *string
			minExp, hasMin := job["minYearsOfExperience"].(float64)
			maxExp, hasMax := job["maxYearsOfExperience"].(float64)
			if hasMin || hasMax {
				var expStr string
				if hasMin && hasMax && minExp != maxExp {
					expStr = fmt.Sprintf("%d-%d tahun", int(minExp), int(maxExp))
				} else if hasMin {
					expStr = fmt.Sprintf("%d+ tahun", int(minExp))
				} else if hasMax {
					expStr = fmt.Sprintf("hingga %d tahun", int(maxExp))
				}
				if expStr != "" {
					experience = &expStr
				}
			}

			education := utils.DecodeGlintsEducation(job["educationLevel"])
			var jobDesc *string

			if s.matchesKeywords(title) && !s.IsSeen(s.SourceName(), rawID) {
				detailDesc, _ := s.fetchJobDetail(rawID)
				if detailDesc != "" {
					jobDesc = &detailDesc
				}
			}

			jobURL := fmt.Sprintf("https://glints.com/id/opportunities/jobs/%s", rawID)
			itemModel := model.Job{
				RawID:           rawID,
				Source:          s.SourceName(),
				Title:           utils.SanitizeText(title),
				Company:         utils.SanitizeText(companyName),
				LogoURL:         logoURL,
				CompanyIndustry: companyIndustry,
				Location:        utils.SanitizeText(locationStr),
				SalaryMin:       salMin,
				SalaryMax:       salMax,
				SalaryCurrency:  salCurr,
				WorkType:        &jobType,
				WorkMode:        workMode,
				PostedAt:        postedAt,
				Skills:          skillsList,
				Experience:      experience,
				Education:       education,
				JobDescription:  jobDesc,
				URL:             jobURL,
				ScrapedAt:       time.Now().UTC().Format(time.RFC3339),
			}

			scrapedJobs = append(scrapedJobs, itemModel)
			seenJobIDs[rawID] = true
		}
	}

	return scrapedJobs, nil
}
