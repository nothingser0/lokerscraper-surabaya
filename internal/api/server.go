package api

import (
	"bufio"
	_ "embed"
	"encoding/csv"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"net/http"
	"os"
	"path/filepath"
	"sort"
	"strconv"
	"strings"
	"sync"
	"time"

	"lokerscraper-surabaya/internal/config"
	"lokerscraper-surabaya/internal/engine"
	"lokerscraper-surabaya/internal/model"
	"lokerscraper-surabaya/internal/storage"
)

//go:embed dashboard.html
var dashboardHTML []byte

type Server struct {
	cfg           *config.Config
	storage       *storage.StorageService
	runner        *engine.Runner
	lastScrapedAt *string
	mu            sync.RWMutex
}

func NewServer(cfg *config.Config, store *storage.StorageService, runner *engine.Runner) *Server {
	return &Server{
		cfg:     cfg,
		storage: store,
		runner:  runner,
	}
}

func (s *Server) SetLastScrapedAt(t string) {
	s.mu.Lock()
	defer s.mu.Unlock()
	s.lastScrapedAt = &t
}

func (s *Server) GetLastScrapedAt() *string {
	s.mu.RLock()
	defer s.mu.RUnlock()
	return s.lastScrapedAt
}

func (s *Server) RegisterRoutes(mux *http.ServeMux) {
	mux.HandleFunc("/", s.handleRoot)
	mux.HandleFunc("/static/", s.handleStatic)
	mux.HandleFunc("/health", s.handleHealth)
	mux.HandleFunc("/api/trigger", s.handleTrigger)
	mux.HandleFunc("/api/stats", s.handleStats)
	mux.HandleFunc("/api/logs", s.handleLogs)
	mux.HandleFunc("/api/jobs", s.handleJobs)
	mux.HandleFunc("/api/export", s.handleExport)
}

func (s *Server) handleRoot(w http.ResponseWriter, r *http.Request) {
	if r.URL.Path != "/" {
		http.NotFound(w, r)
		return
	}
	w.Header().Set("Content-Type", "text/html; charset=utf-8")
	w.Header().Set("Cache-Control", "no-store, no-cache, must-revalidate, max-age=0")
	w.Header().Set("Pragma", "no-cache")
	w.WriteHeader(http.StatusOK)
	_, _ = w.Write(dashboardHTML)
}

func (s *Server) handleStatic(w http.ResponseWriter, r *http.Request) {
	filename := strings.TrimPrefix(r.URL.Path, "/static/")
	filePath := filepath.Join(s.cfg.StaticDir, filepath.Clean(filename))

	// Prevent directory traversal
	if !strings.HasPrefix(filePath, s.cfg.StaticDir) {
		http.Error(w, "Forbidden", http.StatusForbidden)
		return
	}

	w.Header().Set("Cache-Control", "public, max-age=31536000, immutable")
	http.ServeFile(w, r, filePath)
}

func (s *Server) handleHealth(w http.ResponseWriter, r *http.Request) {
	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]string{
		"status":    "ok",
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

func (s *Server) handleTrigger(w http.ResponseWriter, r *http.Request) {
	configuredToken := strings.TrimSpace(s.cfg.TriggerToken)
	reqToken := strings.TrimSpace(r.Header.Get("X-Trigger-Token"))
	if reqToken == "" {
		reqToken = strings.TrimSpace(r.URL.Query().Get("token"))
	}

	if configuredToken != "" && reqToken != configuredToken {
		w.Header().Set("Content-Type", "application/json")
		w.WriteHeader(http.StatusUnauthorized)
		_ = json.NewEncoder(w).Encode(map[string]string{
			"status":  "error",
			"message": "Unauthorized: invalid or missing trigger token",
		})
		return
	}

	forceParam := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("force")))
	force := forceParam == "1" || forceParam == "true" || forceParam == "yes"

	go func() {
		res, err := s.runner.RunCycle(force)
		nowStr := time.Now().UTC().Format(time.RFC3339)
		s.SetLastScrapedAt(nowStr)
		if err != nil {
			log.Printf("[Server] Error in manual scrape cycle: %v", err)
		} else {
			log.Printf("[Server] Manual scrape finished: %d new jobs found.", res.NewJobsCount)
		}
	}()

	w.Header().Set("Content-Type", "application/json")
	w.WriteHeader(http.StatusAccepted)
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"status":    "started",
		"message":   "Scrape cycle started in background",
		"force":     force,
		"timestamp": time.Now().UTC().Format(time.RFC3339),
	})
}

func (s *Server) handleStats(w http.ResponseWriter, r *http.Request) {
	totalJobs, counts, err := s.storage.GetStatsCounts()
	if err != nil {
		totalJobs = 0
		counts = make(map[string]int)
	}

	platforms := s.runner.GetRegisteredPlatforms()
	sort.Strings(platforms)

	sourceCounts := make(map[string]int)
	for _, p := range platforms {
		sourceCounts[p] = counts[p]
	}

	lastUpdated := s.storage.GetLastUpdated()
	lastScraped := s.GetLastScrapedAt()

	var dbBytes int64
	if fi, err := os.Stat(s.storage.DBPath()); err == nil {
		dbBytes = fi.Size()
	}

	resp := map[string]interface{}{
		"totalJobs":     totalJobs,
		"sourceCounts":  sourceCounts,
		"platforms":     platforms,
		"platformCount": len(platforms),
		"lastUpdated":   lastUpdated,
		"lastScrapedAt": lastScraped,
		"retentionDays": s.cfg.JobRetentionDays,
		"dbBytes":       dbBytes,
		"keywords":      s.cfg.Keywords,
		"locations":     s.cfg.Locations,
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(resp)
}

func (s *Server) handleLogs(w http.ResponseWriter, r *http.Request) {
	linesCount := 40
	if l := r.URL.Query().Get("lines"); l != "" {
		if val, err := strconv.Atoi(l); err == nil {
			linesCount = val
		}
	}
	if linesCount < 1 {
		linesCount = 1
	} else if linesCount > 200 {
		linesCount = 200
	}

	logFile := s.cfg.LogFile
	file, err := os.Open(logFile)
	if err != nil {
		w.Header().Set("Content-Type", "application/json")
		_ = json.NewEncoder(w).Encode(map[string]interface{}{"lines": []string{}})
		return
	}
	defer file.Close()

	const maxTailBytes int64 = 64 * 1024
	skipFirstPartialLine := false
	if fi, err := file.Stat(); err == nil && fi.Size() > maxTailBytes {
		if _, err := file.Seek(-maxTailBytes, io.SeekEnd); err == nil {
			skipFirstPartialLine = true
		}
	}

	var lines []string
	scanner := bufio.NewScanner(file)
	if skipFirstPartialLine {
		_ = scanner.Scan()
	}
	for scanner.Scan() {
		lines = append(lines, scanner.Text())
	}

	start := len(lines) - linesCount
	if start < 0 {
		start = 0
	}
	tail := lines[start:]

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"lines": tail,
	})
}

func (s *Server) handleJobs(w http.ResponseWriter, r *http.Request) {
	keyword := strings.TrimSpace(r.URL.Query().Get("keyword"))
	source := strings.TrimSpace(r.URL.Query().Get("source"))
	fullParam := strings.ToLower(strings.TrimSpace(r.URL.Query().Get("full")))
	includeFull := fullParam == "1" || fullParam == "true"

	var days *int
	if dStr := r.URL.Query().Get("days"); dStr != "" {
		if dVal, err := strconv.Atoi(dStr); err == nil && dVal > 0 {
			days = &dVal
		}
	}

	limit := 500
	if lStr := r.URL.Query().Get("limit"); lStr != "" {
		if lVal, err := strconv.Atoi(lStr); err == nil && lVal > 0 {
			limit = lVal
		}
	}

	offset := 0
	if oStr := r.URL.Query().Get("offset"); oStr != "" {
		if oVal, err := strconv.Atoi(oStr); err == nil && oVal >= 0 {
			offset = oVal
		}
	}

	total, jobs, err := s.storage.QueryJobs(keyword, source, days, limit, offset)
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	if jobs == nil {
		jobs = []model.Job{}
	} else if !includeFull {
		for i := range jobs {
			jobs[i].JobDescription = nil
			jobs[i].CompanyDescription = nil
			jobs[i].Qualifications = nil
		}
	}

	w.Header().Set("Content-Type", "application/json")
	_ = json.NewEncoder(w).Encode(map[string]interface{}{
		"total":  total,
		"limit":  limit,
		"offset": offset,
		"jobs":   jobs,
	})
}

func (s *Server) handleExport(w http.ResponseWriter, r *http.Request) {
	jobs, err := s.storage.LoadJobs()
	if err != nil {
		http.Error(w, err.Error(), http.StatusInternalServerError)
		return
	}

	todayStr := time.Now().Format("2006-01-02")
	w.Header().Set("Content-Type", "text/csv; charset=utf-8")
	w.Header().Set("Content-Disposition", fmt.Sprintf("attachment;filename=jobs-%s.csv", todayStr))

	writer := csv.NewWriter(w)
	_ = writer.Write([]string{"ID", "Source", "Title", "Company", "Location", "Salary", "Work Mode", "URL", "Posted At"})

	for _, j := range jobs {
		salaryStr := ""
		if j.Salary != nil {
			salaryStr = *j.Salary
		} else if j.SalaryMin != nil || j.SalaryMax != nil {
			minS := ""
			if j.SalaryMin != nil {
				minS = fmt.Sprintf("%d", *j.SalaryMin)
			}
			maxS := ""
			if j.SalaryMax != nil {
				maxS = fmt.Sprintf("%d", *j.SalaryMax)
			}
			salaryStr = fmt.Sprintf("%s - %s", minS, maxS)
		}

		_ = writer.Write([]string{
			j.ID,
			j.Source,
			j.Title,
			j.Company,
			j.Location,
			salaryStr,
			j.WorkMode,
			j.URL,
			j.PostedAt,
		})
	}
	writer.Flush()
}
