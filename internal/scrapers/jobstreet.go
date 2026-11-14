package scrapers

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"net/url"
	"regexp"
	"strings"
	"time"

	"github.com/PuerkitoBio/goquery"

	"lokerscraper-surabaya/internal/config"
	"lokerscraper-surabaya/internal/model"
	"lokerscraper-surabaya/internal/utils"
)

var jobStreetValidThroughRe = regexp.MustCompile(`"validThrough"\s*:\s*"([^"]+)"`)

type JobStreetScraper struct {
	*BaseClient
	cfg *config.Config
}

func NewJobStreetScraper(cfg *config.Config) *JobStreetScraper {
	return &JobStreetScraper{
		BaseClient: NewBaseClient(12*time.Second, 1*time.Second),
		cfg:        cfg,
	}
}

func (s *JobStreetScraper) SourceName() string {
	return "JobStreet"
}

func (s *JobStreetScraper) SetSeenIDs(seen map[string]bool) {
	s.SeenIDs = seen
}

func (s *JobStreetScraper) matchesKeywords(title string) bool {
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

func (s *JobStreetScraper) fetchJobDetail(rawID string) (string, *string) {
	detailURL := fmt.Sprintf("https://id.jobstreet.com/job/%s", rawID)
	req, err := http.NewRequest("GET", detailURL, nil)
	if err != nil {
		return "", nil
	}
	req.Header.Set("User-Agent", DefaultUserAgent)

	resp, err := s.DoRequest(req)
	if err != nil {
		return "", nil
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return "", nil
	}

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return "", nil
	}

	var deadline *string
	doc.Find("script[type='application/ld+json']").Each(func(i int, s *goquery.Selection) {
		text := s.Text()
		if m := jobStreetValidThroughRe.FindStringSubmatch(text); len(m) > 1 {
			val := m[1]
			if len(val) >= 10 {
				val = val[:10]
			}
			deadline = &val
		}
	})

	var jobDesc string
	descEl := doc.Find("div[data-automation='jobDescription']")
	if descEl.Length() == 0 {
		descEl = doc.Find("div[class*='jobDescription'], div[class*='Description']")
	}
	if descEl.Length() > 0 {
		htmlStr, _ := descEl.Html()
		jobDesc = utils.CleanDescription(htmlStr)
	}

	return jobDesc, deadline
}

func (s *JobStreetScraper) FetchJobs() ([]model.Job, error) {
	var scrapedJobs []model.Job
	seenJobIDs := make(map[string]bool)
	defaultLoc := "Surabaya"
	if len(s.cfg.Locations) > 0 {
		defaultLoc = s.cfg.Locations[0]
	}

	for _, kw := range s.cfg.Keywords {
		apiURL := fmt.Sprintf("https://id.jobstreet.com/api/jobsearch/v5/search?siteKey=ID-Main&sourcesystem=chalice&where=%s&pageSize=20&keywords=%s",
			url.QueryEscape(defaultLoc), url.QueryEscape(kw))

		req, err := http.NewRequest("GET", apiURL, nil)
		if err != nil {
			continue
		}
		req.Header.Set("User-Agent", DefaultUserAgent)
		req.Header.Set("Accept", "application/json")

		resp, err := s.DoRequest(req)
		if err != nil {
			log.Printf("[JobStreet] Request error for keyword %s: %v", kw, err)
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

			company := "Unknown"
			if adv, ok := job["advertiser"].(map[string]interface{}); ok {
				if d, ok := adv["description"].(string); ok && d != "" {
					company = d
				}
			}

			var logoURL *string
			if branding, ok := job["branding"].(map[string]interface{}); ok {
				if logo, ok := branding["serpLogoUrl"].(string); ok && logo != "" {
					logoURL = &logo
				}
			}

			var companyIndustry *string
			if clsList, ok := job["classifications"].([]interface{}); ok && len(clsList) > 0 {
				if first, ok := clsList[0].(map[string]interface{}); ok {
					if cObj, ok := first["classification"].(map[string]interface{}); ok {
						if d, ok := cObj["description"].(string); ok && d != "" {
							companyIndustry = &d
						}
					}
				}
			}

			locationStr := defaultLoc
			if locs, ok := job["locations"].([]interface{}); ok && len(locs) > 0 {
				if first, ok := locs[0].(map[string]interface{}); ok {
					if lbl, ok := first["label"].(string); ok && lbl != "" {
						locationStr = lbl
					}
				}
			}

			salaryRaw, _ := job["salaryLabel"].(string)
			salMin, salMax := utils.ParseSalaryLabel(salaryRaw)
			var salCurr *string
			if salMin != nil || salMax != nil {
				curr := "IDR"
				salCurr = &curr
			}

			workTypes, _ := job["workTypes"].([]interface{})
			rawType := "Full-time"
			if len(workTypes) > 0 {
				rawType = fmt.Sprintf("%v", workTypes[0])
			}
			workType := utils.FormatJobType(rawType)

			workMode := "On-site"
			if arrObj, ok := job["workArrangements"].(map[string]interface{}); ok {
				if dataList, ok := arrObj["data"].([]interface{}); ok {
					for _, d := range dataList {
						s := fmt.Sprintf("%v", d)
						if strings.Contains(strings.ToLower(s), "remote") {
							workMode = "Remote"
						} else if strings.Contains(strings.ToLower(s), "hybrid") {
							workMode = "Hybrid"
						}
					}
				}
			}

			listingDate, _ := job["listingDate"].(string)
			postedAt := time.Now().UTC().Format("2006-01-02")
			if len(listingDate) >= 10 {
				postedAt = listingDate[:10]
			}

			var jobDesc *string
			var appDeadline *string
			if s.matchesKeywords(title) && !s.IsSeen(s.SourceName(), rawID) {
				dDesc, dLine := s.fetchJobDetail(rawID)
				if dDesc != "" {
					jobDesc = &dDesc
				}
				appDeadline = dLine
			}

			if jobDesc == nil {
				var parts []string
				if teaser, ok := job["teaser"].(string); ok && strings.TrimSpace(teaser) != "" {
					parts = append(parts, strings.TrimSpace(teaser))
				}
				if bullets, ok := job["bulletPoints"].([]interface{}); ok {
					for _, b := range bullets {
						if bStr, ok := b.(string); ok && strings.TrimSpace(bStr) != "" {
							parts = append(parts, "• "+strings.TrimSpace(bStr))
						}
					}
				}
				if len(parts) > 0 {
					jStr := strings.Join(parts, "\n\n")
					jobDesc = &jStr
				}
			}

			jobURL := fmt.Sprintf("https://id.jobstreet.com/job/%s", rawID)
			scrapedJobs = append(scrapedJobs, model.Job{
				RawID:               rawID,
				Source:              s.SourceName(),
				Title:               utils.SanitizeText(title),
				Company:             utils.SanitizeText(company),
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
				JobDescription:      jobDesc,
				URL:                 jobURL,
				ScrapedAt:           time.Now().UTC().Format(time.RFC3339),
			})

			seenJobIDs[rawID] = true
		}
	}

	return scrapedJobs, nil
}
