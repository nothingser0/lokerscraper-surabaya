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

type TechInAsiaScraper struct {
	*BaseClient
	cfg *config.Config
}

func NewTechInAsiaScraper(cfg *config.Config) *TechInAsiaScraper {
	return &TechInAsiaScraper{
		BaseClient: NewBaseClient(12*time.Second, 1*time.Second),
		cfg:        cfg,
	}
}

func (s *TechInAsiaScraper) SourceName() string {
	return "TechInAsia"
}

func (s *TechInAsiaScraper) SetSeenIDs(seen map[string]bool) {
	s.SeenIDs = seen
}

func (s *TechInAsiaScraper) FetchJobs() ([]model.Job, error) {
	var scrapedJobs []model.Job
	seenJobIDs := make(map[string]bool)

	for _, kw := range s.cfg.Keywords {
		apiURL := fmt.Sprintf("https://www.techinasia.com/api/2.0/job-postings?query=%s&country_name=Indonesia&page=1&per_page=20",
			url.QueryEscape(kw))

		req, err := http.NewRequest("GET", apiURL, nil)
		if err != nil {
			continue
		}
		req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
		req.Header.Set("Accept", "application/json")
		req.Header.Set("Referer", "https://www.techinasia.com/jobs")

		resp, err := s.DoRequest(req)
		if err != nil {
			log.Printf("[TechInAsia] Request error for keyword %s: %v", kw, err)
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

		jobList, _ := parsed["data"].([]interface{})
		for _, item := range jobList {
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

			companyName := "Unknown Company"
			var logoURL *string
			var companyIndustry *string
			if companyData, ok := job["company"].(map[string]interface{}); ok {
				if cname, ok := companyData["name"].(string); ok && cname != "" {
					companyName = cname
				}
				if logo, ok := companyData["logo_url"].(string); ok && logo != "" {
					logoURL = &logo
				}
				if ind, ok := companyData["industry"].(string); ok && ind != "" {
					companyIndustry = &ind
				}
			}

			locationStr := "Indonesia"
			if locs, ok := job["locations"].([]interface{}); ok && len(locs) > 0 {
				var locNames []string
				for _, l := range locs {
					if lMap, ok := l.(map[string]interface{}); ok {
						if n, ok := lMap["name"].(string); ok && n != "" {
							locNames = append(locNames, n)
						}
					}
				}
				if len(locNames) > 0 {
					locationStr = strings.Join(locNames, ", ")
				}
			}

			isRemote, _ := job["is_remote"].(bool)
			workArrangement := strings.ToLower(fmt.Sprintf("%v", job["work_arrangement"]))
			workMode := "On-site"
			if isRemote || strings.Contains(workArrangement, "remote") {
				workMode = "Remote"
			} else if strings.Contains(workArrangement, "hybrid") {
				workMode = "Hybrid"
			}

			var workType *string
			if jt, ok := job["job_type"].(map[string]interface{}); ok {
				if n, ok := jt["name"].(string); ok && n != "" {
					f := utils.FormatJobType(n)
					workType = &f
				}
			}

			var salMin, salMax *int
			if sm, ok := job["salary_min"].(float64); ok && sm > 0 {
				ism := int(sm)
				salMin = &ism
			}
			if sm, ok := job["salary_max"].(float64); ok && sm > 0 {
				ism := int(sm)
				salMax = &ism
			}
			curr := "IDR"
			if currObj, ok := job["currency"].(map[string]interface{}); ok {
				if c, ok := currObj["currency_code"].(string); ok && c != "" {
					curr = c
				}
			}

			postedAt := time.Now().UTC().Format("2006-01-02")
			if ca, ok := job["created_at"].(string); ok && len(ca) >= 10 {
				postedAt = ca[:10]
			}

			rawDesc, _ := job["description"].(string)
			var jobDesc *string
			if cl := utils.CleanDescription(rawDesc); cl != "" {
				jobDesc = &cl
			}

			jobURL := fmt.Sprintf("https://www.techinasia.com/jobs/%s", rawID)

			scrapedJobs = append(scrapedJobs, model.Job{
				RawID:           rawID,
				Source:          s.SourceName(),
				Title:           utils.SanitizeText(title),
				Company:         utils.SanitizeText(companyName),
				LogoURL:         logoURL,
				CompanyIndustry: companyIndustry,
				Location:        utils.SanitizeText(locationStr),
				SalaryMin:       salMin,
				SalaryMax:       salMax,
				SalaryCurrency:  &curr,
				WorkType:        workType,
				WorkMode:        workMode,
				PostedAt:        postedAt,
				JobDescription:  jobDesc,
				URL:             jobURL,
				ScrapedAt:       time.Now().UTC().Format(time.RFC3339),
			})

			seenJobIDs[rawID] = true
		}
	}

	return scrapedJobs, nil
}
