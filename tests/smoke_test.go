package tests

import (
	"encoding/json"
	"net/http"
	"net/http/httptest"
	"testing"

	"lokerscraper-surabaya/internal/api"
	"lokerscraper-surabaya/internal/config"
	"lokerscraper-surabaya/internal/engine"
	"lokerscraper-surabaya/internal/model"
	"lokerscraper-surabaya/internal/storage"
)

func TestStorageAndAPI(t *testing.T) {
	cfg := config.LoadConfig()
	engine.InitFilter(cfg)

	store, err := storage.NewStorageService(cfg)
	if err != nil {
		t.Fatalf("Failed to initialize storage: %v", err)
	}
	defer store.Close()

	// 1. Storage tests
	seedJobs := []model.Job{
		{
			ID:       "test_1",
			Source:   "TestPlatform",
			Title:    "Backend Go Developer",
			Company:  "Tech Corp",
			Location: "Surabaya",
			WorkMode: "Hybrid",
			PostedAt: "2026-11-11",
		},
	}
	if err := store.SaveJobs(seedJobs); err != nil {
		t.Fatalf("Failed to save test jobs: %v", err)
	}

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
