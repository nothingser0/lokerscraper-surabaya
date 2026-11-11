package scrapers

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"

	"lokerscraper-surabaya/internal/config"
	"lokerscraper-surabaya/internal/model"
	"lokerscraper-surabaya/internal/utils"
)

type GlintsScraper struct {
	*BaseClient
	cfg *config.Config
}

func NewGlintsScraper(cfg *config.Config) *GlintsScraper {
	return &GlintsScraper{
		BaseClient: NewBaseClient(12*time.Second, 500*time.Millisecond),
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

func (s *GlintsScraper) fetchJobDetail(rawID string) (string, string) {
	apiURL := fmt.Sprintf("https://glints.com/api/jobs/%s", rawID)
	req, err := http.NewRequest("GET", apiURL, nil)
	if err != nil {
		return "", ""
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	req.Header.Set("Accept", "application/json")

	resp, err := s.DoRequest(req)
	if err != nil || resp.StatusCode != 200 {
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

func (s *GlintsScraper) FetchJobs() ([]model.Job, error) {
	var scrapedJobs []model.Job
	seenJobIDs := make(map[string]bool)
	defaultLoc := "Surabaya"
	if len(s.cfg.Locations) > 0 {
		defaultLoc = s.cfg.Locations[0]
	}

	for _, kw := range s.cfg.Keywords {
		searchURL := fmt.Sprintf("https://glints.com/id/opportunities/jobs/explore?keyword=%s&country=ID&locationName=%s",
			url.QueryEscape(kw), url.QueryEscape(defaultLoc))

		req, err := http.NewRequest("GET", searchURL, nil)
		if err != nil {
			continue
		}
		req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
		req.Header.Set("Accept", "text/html,application/xhtml+xml")
		req.Header.Set("Accept-Language", "en-US,en;q=0.9")

		resp, err := s.DoRequest(req)
		if err != nil {
			log.Printf("[Glints] Request error for keyword %s: %v", kw, err)
			continue
		}
		if resp.StatusCode != 200 {
			resp.Body.Close()
			continue
		}

		doc, err := goquery.NewDocumentFromReader(resp.Body)
		resp.Body.Close()
		if err != nil {
			continue
		}

		scriptText := doc.Find("script#__NEXT_DATA__").Text()
		if scriptText == "" {
			continue
		}

		var nextData map[string]interface{}
		if err := json.Unmarshal([]byte(scriptText), &nextData); err != nil {
			continue
		}

		props, _ := nextData["props"].(map[string]interface{})
		pageProps, _ := props["pageProps"].(map[string]interface{})
		if pageProps == nil {
			continue
		}

		var jobsData []interface{}
		if initJobs, ok := pageProps["initialJobs"].(map[string]interface{}); ok {
			if inPage, ok := initJobs["jobsInPage"].([]interface{}); ok {
				jobsData = inPage
			}
		} else if initList, ok := pageProps["initialJobs"].([]interface{}); ok {
			jobsData = initList
		}

		if len(jobsData) == 0 {
			if initState, ok := pageProps["initialState"].(map[string]interface{}); ok {
				if jobsObj, ok := initState["jobs"].(map[string]interface{}); ok {
					if dataList, ok := jobsObj["data"].([]interface{}); ok {
						jobsData = dataList
					}
				}
			}
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
					logoURL = &logo
				} else if logo, ok := companyInfo["logoUrl"].(string); ok && logo != "" {
					logoURL = &logo
				}
				if ind, ok := companyInfo["industry"].(string); ok && ind != "" {
					companyIndustry = &ind
				}
			}

			locationStr := defaultLoc
			if locInfo, ok := job["location"].(map[string]interface{}); ok {
				if name, ok := locInfo["name"].(string); ok && name != "" {
					locationStr = name
				} else if name, ok := locInfo["formattedName"].(string); ok && name != "" {
					locationStr = name
				}
			}

			var salMin, salMax *int
			var salCurr *string
			if salaries, ok := job["salaries"].(map[string]interface{}); ok {
				if minV, ok := salaries["minSalary"].(float64); ok && minV > 0 {
					im := int(minV)
					salMin = &im
				}
				if maxV, ok := salaries["maxSalary"].(float64); ok && maxV > 0 {
					im := int(maxV)
					salMax = &im
				}
				if curr, ok := salaries["currency"].(string); ok && curr != "" {
					salCurr = &curr
				}
			}

			arrangement := strings.ToUpper(fmt.Sprintf("%v %v", job["workArrangementOption"], job["workMode"]))
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
						if name, ok := skMap["name"].(string); ok && name != "" {
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
			rawDesc, _ := job["description"].(string)
			var jobDesc *string
			if cl := utils.CleanDescription(rawDesc); cl != "" {
				jobDesc = &cl
			}

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
