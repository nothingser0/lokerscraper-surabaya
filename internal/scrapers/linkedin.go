package scrapers

import (
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

var (
	linkedInURNRe  = regexp.MustCompile(`jobPosting:(\d+)`)
	linkedInViewRe = regexp.MustCompile(`view/(\d+)`)
)

type LinkedInScraper struct {
	*BaseClient
	cfg *config.Config
}

func NewLinkedInScraper(cfg *config.Config) *LinkedInScraper {
	return &LinkedInScraper{
		BaseClient: NewBaseClient(15*time.Second, 1500*time.Millisecond),
		cfg:        cfg,
	}
}

func (s *LinkedInScraper) SourceName() string {
	return "LinkedIn"
}

func (s *LinkedInScraper) SetSeenIDs(seen map[string]bool) {
	s.SeenIDs = seen
}

func (s *LinkedInScraper) matchesKeywords(title string) bool {
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

func (s *LinkedInScraper) fetchJobDetail(rawID string) (string, *string, *string) {
	detailURL := fmt.Sprintf("https://www.linkedin.com/jobs-guest/jobs/api/jobPosting/%s", rawID)
	req, err := http.NewRequest("GET", detailURL, nil)
	if err != nil {
		return "", nil, nil
	}
	req.Header.Set("User-Agent", DefaultUserAgent)

	resp, err := s.DoRequest(req)
	if err != nil {
		return "", nil, nil
	}
	defer resp.Body.Close()
	if resp.StatusCode != 200 {
		return "", nil, nil
	}

	doc, err := goquery.NewDocumentFromReader(resp.Body)
	if err != nil {
		return "", nil, nil
	}

	var jobDesc string
	descEl := doc.Find("div[class*='show-more-less-html__markup'], div[class*='description__text']")
	if descEl.Length() > 0 {
		htmlStr, _ := descEl.Html()
		jobDesc = utils.CleanDescription(htmlStr)
	}

	var experience *string
	var industry *string
	doc.Find("li[class*='description__job-criteria-item']").Each(func(i int, s *goquery.Selection) {
		h := strings.ToLower(strings.TrimSpace(s.Find("h3").Text()))
		v := strings.TrimSpace(s.Find("span").Text())
		if strings.Contains(h, "seniority") {
			if v != "" && !strings.EqualFold(v, "not applicable") {
				experience = &v
			}
		} else if strings.Contains(h, "industry") || strings.Contains(h, "industries") {
			if v != "" {
				industry = &v
			}
		}
	})

	return jobDesc, experience, industry
}

func (s *LinkedInScraper) FetchJobs() ([]model.Job, error) {
	var scrapedJobs []model.Job
	seenJobIDs := make(map[string]bool)
	defaultLoc := "Surabaya"
	if len(s.cfg.Locations) > 0 {
		defaultLoc = s.cfg.Locations[0]
	}

	for _, kw := range s.cfg.Keywords {
		searchURL := fmt.Sprintf("https://www.linkedin.com/jobs-guest/jobs/api/seeMoreJobPostings/search?keywords=%s&location=%s&start=0",
			url.QueryEscape(kw), url.QueryEscape(defaultLoc))

		req, err := http.NewRequest("GET", searchURL, nil)
		if err != nil {
			continue
		}
		req.Header.Set("User-Agent", DefaultUserAgent)
		req.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")

		resp, err := s.DoRequest(req)
		if err != nil {
			log.Printf("[LinkedIn] Request error for keyword %s: %v", kw, err)
			continue
		}

		if resp.StatusCode == 429 {
			log.Printf("[LinkedIn] Rate limited (429) for keyword %s; backing off 60s...", kw)
			resp.Body.Close()
			time.Sleep(60 * time.Second)
			retryReq, retryErr := http.NewRequest("GET", searchURL, nil)
			if retryErr != nil {
				break
			}
			retryReq.Header.Set("User-Agent", DefaultUserAgent)
			retryReq.Header.Set("Accept", "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8")
			resp, err = s.DoRequest(retryReq)
			if err != nil || resp.StatusCode == 429 {
				if resp != nil {
					resp.Body.Close()
				}
				log.Printf("[LinkedIn] Still rate limited; stopping LinkedIn cycle.")
				break
			}
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

		doc.Find("li").Each(func(i int, card *goquery.Selection) {
			rawID := ""
			if urn, exists := card.Find("div[data-entity-urn]").Attr("data-entity-urn"); exists {
				if m := linkedInURNRe.FindStringSubmatch(urn); len(m) > 1 {
					rawID = m[1]
				}
			}
			if rawID == "" {
				if link, exists := card.Find("a[class*='base-card__full-link'], a[class*='job-search-card__link']").Attr("href"); exists {
					if m := linkedInViewRe.FindStringSubmatch(link); len(m) > 1 {
						rawID = m[1]
					}
				}
			}

			if rawID == "" || seenJobIDs[rawID] {
				return
			}

			title := strings.TrimSpace(card.Find("h3[class*='base-search-card__title'], h3[class*='job-search-card__title']").First().Text())
			if title == "" {
				title = "Untitled"
			}

			company := strings.TrimSpace(card.Find("h4[class*='base-search-card__subtitle'], h4[class*='job-search-card__subtitle'], a[class*='hidden-nested-link']").First().Text())
			if company == "" {
				company = "Unknown"
			}

			var logoURL *string
			img := card.Find("img").First()
			if delayed, exists := img.Attr("data-delayed-url"); exists && delayed != "" {
				logoURL = &delayed
			} else if src, exists := img.Attr("src"); exists && src != "" {
				logoURL = &src
			}

			locStr := strings.TrimSpace(card.Find("span[class*='job-search-card__location']").First().Text())
			if locStr == "" {
				locStr = defaultLoc
			}

			jobURL := fmt.Sprintf("https://www.linkedin.com/jobs/view/%s", rawID)
			if link, exists := card.Find("a[class*='base-card__full-link'], a[class*='job-search-card__link']").Attr("href"); exists && link != "" {
				jobURL = strings.Split(link, "?")[0]
			}

			postedAt := time.Now().UTC().Format("2006-01-02")
			timeEl := card.Find("time")
			if dt, exists := timeEl.Attr("datetime"); exists && len(dt) >= 10 {
				postedAt = dt[:10]
			}

			titleLower := strings.ToLower(title)
			workMode := "On-site"
			if strings.Contains(titleLower, "remote") {
				workMode = "Remote"
			} else if strings.Contains(titleLower, "hybrid") {
				workMode = "Hybrid"
			}

			workType := "Full-time"
			var jobDesc *string
			var experience *string
			var companyIndustry *string

			if s.matchesKeywords(title) && !s.IsSeen(s.SourceName(), rawID) {
				dDesc, dExp, dInd := s.fetchJobDetail(rawID)
				if dDesc != "" {
					jobDesc = &dDesc
				}
				experience = dExp
				companyIndustry = dInd
			}

			scrapedJobs = append(scrapedJobs, model.Job{
				RawID:           rawID,
				Source:          s.SourceName(),
				Title:           utils.SanitizeText(title),
				Company:         utils.SanitizeText(company),
				LogoURL:         logoURL,
				CompanyIndustry: companyIndustry,
				Location:        utils.SanitizeText(locStr),
				WorkType:        &workType,
				WorkMode:        workMode,
				PostedAt:        postedAt,
				Experience:      experience,
				JobDescription:  jobDesc,
				URL:             jobURL,
				ScrapedAt:       time.Now().UTC().Format(time.RFC3339),
			})

			seenJobIDs[rawID] = true
		})
	}

	return scrapedJobs, nil
}
