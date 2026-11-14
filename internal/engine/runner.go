package engine

import (
	"fmt"
	"log"
	"sync"

	"lokerscraper-surabaya/internal/config"
	"lokerscraper-surabaya/internal/model"
	"lokerscraper-surabaya/internal/notifiers"
	"lokerscraper-surabaya/internal/scrapers"
	"lokerscraper-surabaya/internal/storage"
)

type CycleResult struct {
	ScrapedTotal  int         `json:"scraped_total"`
	FilteredTotal int         `json:"filtered_total"`
	NewJobsCount  int         `json:"new_jobs_count"`
	NewJobs       []model.Job `json:"new_jobs"`
}

type Runner struct {
	cfg      *config.Config
	storage  *storage.StorageService
	scrapers []scrapers.Scraper
	mu       sync.Mutex
	running  bool
}

func NewRunner(cfg *config.Config, store *storage.StorageService) *Runner {
	scList := []scrapers.Scraper{
		scrapers.NewJobStreetScraper(cfg),
		scrapers.NewLinkedInScraper(cfg),
		scrapers.NewKalibrrScraper(cfg),
		scrapers.NewGlintsScraper(cfg),
		scrapers.NewSejutaCitaScraper(cfg),
		scrapers.NewKarirScraper(cfg),
		scrapers.NewTechInAsiaScraper(cfg),
		scrapers.NewRemoteOKScraper(cfg),
	}

	return &Runner{
		cfg:      cfg,
		storage:  store,
		scrapers: scList,
	}
}

func (r *Runner) GetRegisteredPlatforms() []string {
	var names []string
	for _, s := range r.scrapers {
		names = append(names, s.SourceName())
	}
	return names
}

func (r *Runner) RunCycle(force bool) (CycleResult, error) {
	r.mu.Lock()
	if r.running {
		r.mu.Unlock()
		return CycleResult{}, fmt.Errorf("a scrape cycle is already in progress")
	}
	r.running = true
	r.mu.Unlock()

	defer func() {
		r.mu.Lock()
		r.running = false
		r.mu.Unlock()
	}()

	log.Printf("[Runner] Starting scrape cycle (force=%v, workers=%d)...", force, r.cfg.MaxWorkers)

	seenIDs := r.storage.LoadSeenIDs()
	for _, sc := range r.scrapers {
		sc.SetSeenIDs(seenIDs)
	}

	type scraperResult struct {
		name    string
		success bool
		jobs    []model.Job
		err     error
	}

	maxWorkers := r.cfg.MaxWorkers
	if maxWorkers <= 0 {
		maxWorkers = 2
	}

	jobsChan := make(chan scrapers.Scraper, len(r.scrapers))
	resultsChan := make(chan scraperResult, len(r.scrapers))

	var wg sync.WaitGroup
	for w := 0; w < maxWorkers; w++ {
		wg.Add(1)
		go func() {
			defer wg.Done()
			for sc := range jobsChan {
				sName := sc.SourceName()
				log.Printf("[Runner] Starting scraper: %s", sName)
				jobs, err := sc.FetchJobs()
				success := err == nil
				if err != nil {
					log.Printf("[Runner] Error running scraper %s: %v", sName, err)
				} else {
					log.Printf("[Runner] Finished %s: fetched %d jobs", sName, len(jobs))
				}
				resultsChan <- scraperResult{
					name:    sName,
					success: success,
					jobs:    jobs,
					err:     err,
				}
			}
		}()
	}

	for _, sc := range r.scrapers {
		jobsChan <- sc
	}
	close(jobsChan)

	wg.Wait()
	close(resultsChan)

	var rawJobs []model.Job
	var persistentAlerts []string

	for res := range resultsChan {
		streak := r.storage.RecordScraperRun(res.name, res.success)
		if len(res.jobs) > 0 {
			rawJobs = append(rawJobs, res.jobs...)
		}
		if !res.success {
			if streak >= 3 {
				persistentAlerts = append(persistentAlerts, fmt.Sprintf("%s (Gagal %dx berturut-turut): %v", res.name, streak, res.err))
			}
		}
	}

	scrapedTotal := len(rawJobs)
	filteredJobs := FilterJobs(rawJobs)
	filteredTotal := len(filteredJobs)

	for i := range filteredJobs {
		j := &filteredJobs[i]
		if j.Source == "" {
			j.Source = "Unknown"
		}
		if j.ID == "" {
			rawID := j.RawID
			if rawID == "" {
				rawID = j.URL
			}
			if rawID == "" {
				rawID = j.Title
			}
			j.ID = GenerateJobID(j.Source, rawID)
		}
	}

	existingSeenIDs := r.storage.LoadSeenIDs()
	newJobs, newIDs := DeduplicateJobs(filteredJobs, existingSeenIDs)
	newJobsCount := len(newJobs)

	if newJobsCount > 0 {
		_ = r.storage.SaveJobs(newJobs)
		_ = r.storage.SaveSeenIDs(newIDs)
		r.storage.LogDailyJobs(newJobs)
		notifiers.NotifyNewJobs(r.cfg, newJobs)
	}

	if force && len(filteredJobs) > 0 {
		notifiers.NotifyNewJobs(r.cfg, filteredJobs)
	}

	if len(persistentAlerts) > 0 {
		notifiers.NotifyScraperError(r.cfg, persistentAlerts)
	}

	_ = r.storage.CleanupOldJobs(r.cfg.JobRetentionDays)
	_ = r.storage.TrimSeenIDs(10000, 5000)
	r.storage.TrimLogFile(r.cfg.LogFile, 2*1024*1024, 512*1024)

	log.Printf("[Runner] Scrape cycle completed: %d raw -> %d filtered -> %d new jobs saved.",
		scrapedTotal, filteredTotal, newJobsCount)

	return CycleResult{
		ScrapedTotal:  scrapedTotal,
		FilteredTotal: filteredTotal,
		NewJobsCount:  newJobsCount,
		NewJobs:       newJobs,
	}, nil
}
