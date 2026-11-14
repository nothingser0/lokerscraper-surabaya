package tests

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"os"
	"path/filepath"
	"testing"
	"time"

	"lokerscraper-surabaya/internal/api"
	"lokerscraper-surabaya/internal/config"
	"lokerscraper-surabaya/internal/engine"
	"lokerscraper-surabaya/internal/model"
	"lokerscraper-surabaya/internal/scrapers"
	"lokerscraper-surabaya/internal/storage"
)

func TestStorageAndAPI(t *testing.T) {
	tempDir := t.TempDir()

	cfg := config.LoadConfig()
	cfg.DataDir = tempDir
	cfg.LogsDir = tempDir
	cfg.LogFile = filepath.Join(tempDir, "scraper.log")
	cfg.StaticDir = filepath.Join("..", "static")

	engine.InitFilter(cfg)

	store, err := storage.NewStorageService(cfg)
	if err != nil {
		t.Fatalf("Failed to initialize storage: %v", err)
	}
	defer store.Close()

	// 1. Storage & Deduplication tests
	salMin := 6000000
	salMax := 8000000
	seedJobs := []model.Job{
		{
			RawID:     "raw_1",
			Source:    "Glints",
			Title:     "Backend Go Developer",
			Company:   "Tech Corp",
			Location:  "Surabaya",
			SalaryMin: &salMin,
			SalaryMax: &salMax,
			WorkMode:  "Hybrid",
			PostedAt:  "2026-11-11",
		},
		{
			// Repost / cross-platform duplicate with different RawID but identical Title + Company + Location
			RawID:    "raw_999",
			Source:   "LinkedIn",
			Title:    "Backend Go Developer",
			Company:  "Tech Corp",
			Location: "Surabaya",
			WorkMode: "Hybrid",
			PostedAt: "2026-11-11",
		},
	}

	seen := store.LoadSeenIDs()
	deduped, newIDs := engine.DeduplicateJobs(seedJobs, seen)
	if len(deduped) != 1 {
		t.Fatalf("Expected DeduplicateJobs to keep 1 unique job out of 2 identical jobs, got %d", len(deduped))
	}

	if err := store.SaveJobs(deduped); err != nil {
		t.Fatalf("Failed to save test jobs: %v", err)
	}
	_ = store.SaveSeenIDs(newIDs)

	total, jobs, err := store.QueryJobs("backend", "", nil, 5, 0)
	if err != nil {
		t.Fatalf("QueryJobs failed: %v", err)
	}
	if total < 1 || len(jobs) < 1 {
		t.Fatalf("Expected at least 1 job, got total=%d, jobs=%d", total, len(jobs))
	}

	// 2. Scraper registry test
	runner := engine.NewRunner(cfg, store)
	platforms := runner.GetRegisteredPlatforms()
	if len(platforms) != 8 {
		t.Fatalf("Expected 8 scrapers registered, got %d: %v", len(platforms), platforms)
	}

	// 3. API Handlers test
	server := api.NewServer(cfg, store, runner)
	mux := http.NewServeMux()
	server.RegisterRoutes(mux)

	// Health
	req := httptest.NewRequest("GET", "/health", nil)
	w := httptest.NewRecorder()
	mux.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("/health returned code %d", w.Code)
	}

	// Stats
	req = httptest.NewRequest("GET", "/api/stats", nil)
	w = httptest.NewRecorder()
	mux.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("/api/stats returned code %d", w.Code)
	}
	var stats map[string]interface{}
	if err := json.Unmarshal(w.Body.Bytes(), &stats); err != nil {
		t.Fatalf("Failed to parse /api/stats: %v", err)
	}
	if stats["platformCount"].(float64) != 8 {
		t.Fatalf("Expected platformCount=8, got %v", stats["platformCount"])
	}

	// Jobs
	req = httptest.NewRequest("GET", "/api/jobs?limit=2", nil)
	w = httptest.NewRecorder()
	mux.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("/api/jobs returned code %d", w.Code)
	}

	// Root dashboard
	req = httptest.NewRequest("GET", "/", nil)
	w = httptest.NewRecorder()
	mux.ServeHTTP(w, req)
	if w.Code != http.StatusOK {
		t.Fatalf("/ dashboard returned code %d", w.Code)
	}
	if len(w.Body.String()) < 500 {
		t.Fatalf("Dashboard HTML response too short")
	}

	t.Logf("All Go smoke tests passed successfully!")
}

func TestGlintsLive(t *testing.T) {
	if os.Getenv("LIVE_TEST") == "" {
		t.Skip("Skipping live network test (set LIVE_TEST=1 to run)")
	}
	cfg := config.LoadConfig()
	engine.InitFilter(cfg)

	for _, sc := range []scrapers.Scraper{
		scrapers.NewKalibrrScraper(cfg),
		scrapers.NewSejutaCitaScraper(cfg),
		scrapers.NewTechInAsiaScraper(cfg),
	} {
		start := time.Now()
		jobs, err := sc.FetchJobs()
		filtered := engine.FilterJobs(jobs)
		t.Logf("[VERIFIED] %-12s | elapsed=%-8v | raw=%-3d | filtered=%-3d | err=%v",
			sc.SourceName(), time.Since(start).Round(time.Millisecond), len(jobs), len(filtered), err)
	}
}
