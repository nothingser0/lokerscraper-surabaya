package scrapers

import (
	"encoding/json"
	"fmt"
	"log"
	"net/http"
	"time"

	"lokerscraper-surabaya/internal/config"
	"lokerscraper-surabaya/internal/model"
	"lokerscraper-surabaya/internal/utils"
)

type RemoteOKScraper struct {
	*BaseClient
	cfg *config.Config
}

func NewRemoteOKScraper(cfg *config.Config) *RemoteOKScraper {
	return &RemoteOKScraper{
		BaseClient: NewBaseClient(15*time.Second, 2*time.Second),
		cfg:        cfg,
	}
}

func (s *RemoteOKScraper) SourceName() string {
	return "RemoteOK"
}

func (s *RemoteOKScraper) SetSeenIDs(seen map[string]bool) {
	s.SeenIDs = seen
}

func (s *RemoteOKScraper) FetchJobs() ([]model.Job, error) {
	var scrapedJobs []model.Job
	seenJobIDs := make(map[string]bool)

	endpoint := "https://remoteok.com/api"
	req, err := http.NewRequest("GET", endpoint, nil)
	if err != nil {
		return nil, err
	}
	req.Header.Set("User-Agent", "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36")
	req.Header.Set("Accept", "application/json")

	resp, err := s.DoRequest(req)
	if err != nil {
		log.Printf("[RemoteOK] Request error: %v", err)
		return nil, err
	}
	if resp.StatusCode != 200 {
		resp.Body.Close()
		return nil, fmt.Errorf("remoteok status %d", resp.StatusCode)
	}

	body, err := ReadBody(resp)
	if err != nil {
		return nil, err
	}

	var payload []interface{}
	if err := json.Unmarshal(body, &payload); err != nil {
		return nil, err
	}

	for _, item := range payload {
		job, ok := item.(map[string]interface{})
		if !ok || job["id"] == nil || job["position"] == nil {
			continue
		}

		rawID := fmt.Sprintf("%v", job["id"])
		if rawID == "" || seenJobIDs[rawID] {
			continue
		}

		title, _ := job["position"].(string)
		company, _ := job["company"].(string)
		if company == "" {
			company = "Unknown Company"
		}

		var logoURL *string
		if logo, ok := job["company_logo"].(string); ok && logo != "" {
			logoURL = &logo
		}

		locationStr, _ := job["location"].(string)
		if locationStr == "" {
			locationStr = "Remote, Worldwide"
		}

		jobURL, _ := job["url"].(string)
		if jobURL == "" {
			jobURL = fmt.Sprintf("https://remoteok.com/remote-jobs/%s", rawID)
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
		curr := "USD"

		postedAt := time.Now().UTC().Format("2006-01-02")
		if epoch, ok := job["epoch"].(float64); ok && epoch > 0 {
			postedAt = time.Unix(int64(epoch), 0).UTC().Format("2006-01-02")
		} else if dateRaw, ok := job["date"].(string); ok && len(dateRaw) >= 10 {
			postedAt = dateRaw[:10]
		}

		rawDesc, _ := job["description"].(string)
		var jobDesc *string
		if cl := utils.CleanDescription(rawDesc); cl != "" {
			jobDesc = &cl
		}

		workType := "Full-time"
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
			WorkType:       &workType,
			WorkMode:       "Remote",
			PostedAt:       postedAt,
			JobDescription: jobDesc,
			URL:            jobURL,
			ScrapedAt:      time.Now().UTC().Format(time.RFC3339),
		})

		seenJobIDs[rawID] = true
	}

	return scrapedJobs, nil
}
