package scrapers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"lokerscraper-surabaya/internal/config"
	"lokerscraper-surabaya/internal/model"
	"lokerscraper-surabaya/internal/utils"
)

type KarirScraper struct {
	*BaseClient
	cfg *config.Config
}

func NewKarirScraper(cfg *config.Config) *KarirScraper {
	return &KarirScraper{
		BaseClient: NewBaseClient(12*time.Second, 1*time.Second),
		cfg:        cfg,
	}
}

func (s *KarirScraper) SourceName() string {
	return "Karir"
}

func (s *KarirScraper) SetSeenIDs(seen map[string]bool) {
	s.SeenIDs = seen
}

func (s *KarirScraper) FetchJobs() ([]model.Job, error) {
	var scrapedJobs []model.Job
	seenJobIDs := make(map[string]bool)

	endpoint := "https://gateway2-beta.karir.com/v2/search/opportunities"

	for _, kw := range s.cfg.Keywords {
		payload := map[string]interface{}{
			"keyword": kw,
			"locale":  "id",
			"limit":   20,
			"offset":  0,
		}
		data, err := json.Marshal(payload)
		if err != nil {
			continue
		}

		req, err := http.NewRequest("POST", endpoint, bytes.NewBuffer(data))
		if err != nil {
			continue
		}
		req.Header.Set("User-Agent", DefaultUserAgent)
		req.Header.Set("Content-Type", "application/json")
		req.Header.Set("Accept", "application/json")
		req.Header.Set("Origin", "https://karir.com")
		req.Header.Set("Referer", "https://karir.com/")

		resp, err := s.DoRequest(req)
		if err != nil {
			log.Printf("[Karir] Request error for keyword %s: %v", kw, err)
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

		dataObj, _ := parsed["data"].(map[string]interface{})
		if dataObj == nil {
			continue
		}
		oppList, _ := dataObj["opportunities"].([]interface{})
		for _, item := range oppList {
			job, ok := item.(map[string]interface{})
			if !ok {
				continue
			}

			rawID := fmt.Sprintf("%v", job["id"])
			if rawID == "" || seenJobIDs[rawID] {
				continue
			}

			title, _ := job["job_position"].(string)
			if title == "" {
				title = "Untitled"
			}

			company, _ := job["company_name"].(string)
			if company == "" {
				company = "Unknown Company"
			}

			var logoURL *string
			if logo, ok := job["company_logo_url"].(string); ok && logo != "" {
				logoURL = &logo
			}

			locationStr, _ := job["description"].(string)
			if locationStr == "" {
				locationStr = "Indonesia"
			}

			var salMin, salMax *int
			if sm, ok := job["salary_lower"].(float64); ok && sm > 0 {
				ism := int(sm)
				salMin = &ism
			}
			if sm, ok := job["salary_upper"].(float64); ok && sm > 0 {
				ism := int(sm)
				salMax = &ism
			}
			curr := "IDR"

			postedAt := time.Now().UTC().Format("2006-01-02")
			if pRaw, ok := job["posted_at"].(string); ok && len(pRaw) >= 10 {
				postedAt = pRaw[:10]
			}

			jobURL := fmt.Sprintf("https://karir.com/opportunities/%s", rawID)

			scrapedJobs = append(scrapedJobs, model.Job{
				RawID:          rawID,
				Source:         s.SourceName(),
				Title:          utils.SanitizeText(title),
				Company:        utils.SanitizeText(company),
				LogoURL:        logoURL,
				Location:       utils.SanitizeText(locationStr),
				SalaryMin:      salMin,
				SalaryMax:      salMax,
				SalaryCurrency: &curr,
				PostedAt:       postedAt,
				URL:            jobURL,
				ScrapedAt:      time.Now().UTC().Format(time.RFC3339),
			})

			seenJobIDs[rawID] = true
		}
	}

	return scrapedJobs, nil
}
