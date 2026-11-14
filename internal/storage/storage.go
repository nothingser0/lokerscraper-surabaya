package storage

import (
	"database/sql"
	"encoding/json"
	"fmt"
	"io"
	"log"
	"os"
	"path/filepath"
	"strings"
	"sync"
	"time"

	"lokerscraper-surabaya/internal/config"
	"lokerscraper-surabaya/internal/model"

	_ "modernc.org/sqlite"
)

type StorageService struct {
	dbPath  string
	logsDir string
	db      *sql.DB
	mu      sync.Mutex
}

var GlobalStorage *StorageService

func NewStorageService(cfg *config.Config) (*StorageService, error) {
	dbPath := filepath.Join(cfg.DataDir, "jobs.db")
	_ = os.MkdirAll(cfg.DataDir, 0755)
	_ = os.MkdirAll(cfg.LogsDir, 0755)

	db, err := sql.Open("sqlite", dbPath+"?_pragma=journal_mode(WAL)&_pragma=synchronous(NORMAL)&_pragma=busy_timeout(5000)")
	if err != nil {
		return nil, fmt.Errorf("failed to open sqlite database: %w", err)
	}

	// Optimize connection pool for low RAM & thread safety
	db.SetMaxOpenConns(5)
	db.SetMaxIdleConns(2)
	db.SetConnMaxLifetime(time.Hour)

	s := &StorageService{
		dbPath:  dbPath,
		logsDir: cfg.LogsDir,
		db:      db,
	}

	if err := s.initSQLite(); err != nil {
		return nil, err
	}

	GlobalStorage = s
	return s, nil
}

func (s *StorageService) Close() error {
	if s.db != nil {
		return s.db.Close()
	}
	return nil
}

func (s *StorageService) DBPath() string {
	return s.dbPath
}

func (s *StorageService) initSQLite() error {
	queries := []string{
		`CREATE TABLE IF NOT EXISTS jobs (
			id TEXT PRIMARY KEY,
			source TEXT,
			title TEXT,
			company TEXT,
			location TEXT,
			salary TEXT,
			url TEXT,
			posted_at TEXT,
			data_json TEXT,
			created_at TEXT
		);`,
		`CREATE INDEX IF NOT EXISTS idx_jobs_source ON jobs(source);`,
		`CREATE INDEX IF NOT EXISTS idx_jobs_created ON jobs(created_at);`,
		`CREATE TABLE IF NOT EXISTS meta (
			key TEXT PRIMARY KEY,
			value TEXT
		);`,
		`CREATE TABLE IF NOT EXISTS seen_ids (
			id TEXT PRIMARY KEY,
			created_at TEXT
		);`,
		`CREATE INDEX IF NOT EXISTS idx_seen_created ON seen_ids(created_at);`,
	}

	for _, q := range queries {
		if _, err := s.db.Exec(q); err != nil {
			return fmt.Errorf("init sqlite error: %w", err)
		}
	}
	return nil
}

func (s *StorageService) LoadJobs() ([]model.Job, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	rows, err := s.db.Query("SELECT data_json FROM jobs ORDER BY rowid DESC")
	if err != nil {
		return nil, err
	}
	defer rows.Close()

	var jobs []model.Job
	for rows.Next() {
		var dataJSON string
		if err := rows.Scan(&dataJSON); err == nil {
			var job model.Job
			if err := json.Unmarshal([]byte(dataJSON), &job); err == nil {
				jobs = append(jobs, job)
			}
		}
	}
	return jobs, nil
}

func (s *StorageService) QueryJobs(keyword, source string, days *int, limit, offset int) (int, []model.Job, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	var whereClauses []string
	var params []interface{}

	if keyword != "" {
		likeKW := "%" + strings.ToLower(keyword) + "%"
		whereClauses = append(whereClauses, "(LOWER(title) LIKE ? OR LOWER(company) LIKE ? OR LOWER(data_json) LIKE ?)")
		params = append(params, likeKW, likeKW, likeKW)
	}

	if source != "" {
		whereClauses = append(whereClauses, "LOWER(source) = ?")
		params = append(params, strings.ToLower(source))
	}

	if days != nil && *days > 0 {
		cutoff := time.Now().UTC().AddDate(0, 0, -(*days)).Format(time.RFC3339)
		cutoffDate := cutoff[:10]
		whereClauses = append(whereClauses, "(created_at >= ? OR posted_at >= ?)")
		params = append(params, cutoff, cutoffDate)
	}

	whereSQL := ""
	if len(whereClauses) > 0 {
		whereSQL = "WHERE " + strings.Join(whereClauses, " AND ")
	}

	var total int
	countQuery := fmt.Sprintf("SELECT COUNT(*) FROM jobs %s", whereSQL)
	if err := s.db.QueryRow(countQuery, params...).Scan(&total); err != nil {
		return 0, nil, err
	}

	querySQL := fmt.Sprintf("SELECT data_json FROM jobs %s ORDER BY rowid DESC LIMIT ? OFFSET ?", whereSQL)
	queryParams := append(params, limit, offset)
	rows, err := s.db.Query(querySQL, queryParams...)
	if err != nil {
		return 0, nil, err
	}
	defer rows.Close()

	var jobs []model.Job
	for rows.Next() {
		var dataJSON string
		if err := rows.Scan(&dataJSON); err == nil {
			var job model.Job
			if err := json.Unmarshal([]byte(dataJSON), &job); err == nil {
				jobs = append(jobs, job)
			}
		}
	}

	return total, jobs, nil
}

func (s *StorageService) SaveJobs(jobs []model.Job) error {
	if len(jobs) == 0 {
		return nil
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	stmt, err := tx.Prepare(`
		INSERT OR REPLACE INTO jobs (id, source, title, company, location, salary, url, posted_at, data_json, created_at)
		VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
	`)
	if err != nil {
		return err
	}
	defer stmt.Close()

	now := time.Now().UTC().Format(time.RFC3339)

	for _, j := range jobs {
		if j.ID == "" {
			continue
		}
		dataBytes, err := json.Marshal(j)
		if err != nil {
			continue
		}

		var salaryVal *string
		if j.Salary != nil {
			salaryVal = j.Salary
		} else if j.SalaryMin != nil || j.SalaryMax != nil {
			s := fmt.Sprintf("%v - %v", j.SalaryMin, j.SalaryMax)
			salaryVal = &s
		}

		created := j.ScrapedAt
		if created == "" {
			created = now
		}

		_, err = stmt.Exec(
			j.ID,
			j.Source,
			j.Title,
			j.Company,
			j.Location,
			salaryVal,
			j.URL,
			j.PostedAt,
			string(dataBytes),
			created,
		)
		if err != nil {
			log.Printf("[Storage] Error executing insert for job %s: %v", j.ID, err)
		}
	}

	_, _ = tx.Exec("INSERT OR REPLACE INTO meta (key, value) VALUES ('lastUpdated', ?)", now)
	return tx.Commit()
}

func (s *StorageService) GetLastUpdated() *string {
	s.mu.Lock()
	defer s.mu.Unlock()

	var val string
	err := s.db.QueryRow("SELECT value FROM meta WHERE key = 'lastUpdated'").Scan(&val)
	if err != nil {
		return nil
	}
	return &val
}

func (s *StorageService) RecordScraperRun(scraperName string, success bool) int {
	s.mu.Lock()
	defer s.mu.Unlock()

	key := fmt.Sprintf("fail_streak_%s", scraperName)
	var currentFails int
	_ = s.db.QueryRow("SELECT CAST(value AS INTEGER) FROM meta WHERE key = ?", key).Scan(&currentFails)

	newFails := 0
	if !success {
		newFails = currentFails + 1
	}

	_, _ = s.db.Exec("INSERT OR REPLACE INTO meta (key, value) VALUES (?, ?)", key, fmt.Sprintf("%d", newFails))
	return newFails
}

func (s *StorageService) LoadSeenIDs() map[string]bool {
	s.mu.Lock()
	defer s.mu.Unlock()

	ids := make(map[string]bool)
	rows, err := s.db.Query("SELECT id FROM seen_ids")
	if err != nil {
		return ids
	}
	defer rows.Close()

	for rows.Next() {
		var id string
		if err := rows.Scan(&id); err == nil {
			ids[id] = true
		}
	}
	return ids
}

func (s *StorageService) SaveSeenIDs(ids []string) error {
	if len(ids) == 0 {
		return nil
	}

	s.mu.Lock()
	defer s.mu.Unlock()

	tx, err := s.db.Begin()
	if err != nil {
		return err
	}
	defer tx.Rollback()

	stmt, err := tx.Prepare("INSERT OR IGNORE INTO seen_ids (id, created_at) VALUES (?, ?)")
	if err != nil {
		return err
	}
	defer stmt.Close()

	now := time.Now().UTC().Format(time.RFC3339)
	for _, id := range ids {
		_, _ = stmt.Exec(id, now)
	}

	return tx.Commit()
}

func (s *StorageService) CleanupOldJobs(days int) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	cutoff := time.Now().UTC().AddDate(0, 0, -days).Format(time.RFC3339)
	cutoffDate := cutoff[:10]

	res, err := s.db.Exec(`
		DELETE FROM jobs 
		WHERE (created_at IS NOT NULL AND created_at != '' AND created_at < ?)
		   OR (created_at IS NULL AND posted_at IS NOT NULL AND posted_at != '' AND posted_at < ?)
	`, cutoff, cutoffDate)
	if err != nil {
		return err
	}

	if affected, _ := res.RowsAffected(); affected > 0 {
		log.Printf("[Storage] Cleaned up %d old jobs from SQLite.", affected)
		_, _ = s.db.Exec("VACUUM")
	}

	s.cleanupOldDailyLogs(cutoffDate)

	return nil
}

func (s *StorageService) cleanupOldDailyLogs(cutoffDate string) {
	entries, err := os.ReadDir(s.logsDir)
	if err != nil {
		return
	}
	for _, entry := range entries {
		if entry.IsDir() {
			continue
		}
		name := entry.Name()
		if !strings.HasPrefix(name, "jobs-") {
			continue
		}
		var datePart string
		if strings.HasSuffix(name, ".json") {
			datePart = strings.TrimSuffix(strings.TrimPrefix(name, "jobs-"), ".json")
		} else if strings.HasSuffix(name, ".txt") {
			datePart = strings.TrimSuffix(strings.TrimPrefix(name, "jobs-"), ".txt")
		}
		if len(datePart) == 10 && datePart < cutoffDate {
			_ = os.Remove(filepath.Join(s.logsDir, name))
		}
	}
}

func (s *StorageService) TrimLogFile(logPath string, maxBytes, keepBytes int64) {
	fi, err := os.Stat(logPath)
	if err != nil || fi.Size() <= maxBytes {
		return
	}

	f, err := os.Open(logPath)
	if err != nil {
		return
	}
	if _, err := f.Seek(-keepBytes, io.SeekEnd); err != nil {
		f.Close()
		return
	}
	buf := make([]byte, keepBytes)
	n, err := f.Read(buf)
	f.Close()
	if err != nil || n <= 0 {
		return
	}

	trimmed := buf[:n]
	if idx := strings.IndexByte(string(trimmed), '\n'); idx >= 0 && idx+1 < len(trimmed) {
		trimmed = trimmed[idx+1:]
	}

	if wf, err := os.OpenFile(logPath, os.O_WRONLY|os.O_TRUNC, 0644); err == nil {
		_, _ = wf.Write(trimmed)
		wf.Close()
	}
}

func (s *StorageService) TrimSeenIDs(maxLimit, targetLimit int) error {
	s.mu.Lock()
	defer s.mu.Unlock()

	var total int
	if err := s.db.QueryRow("SELECT COUNT(*) FROM seen_ids").Scan(&total); err != nil {
		return err
	}

	if total > maxLimit {
		_, err := s.db.Exec(`
			DELETE FROM seen_ids WHERE id NOT IN (
				SELECT id FROM seen_ids ORDER BY created_at DESC LIMIT ?
			)
		`, targetLimit)
		if err == nil {
			log.Printf("[Storage] Trimmed seen_ids from %d to %d.", total, targetLimit)
		}
		return err
	}
	return nil
}

func (s *StorageService) LogDailyJobs(jobs []model.Job) {
	if len(jobs) == 0 {
		return
	}

	todayStr := time.Now().Format("2006-01-02")
	jsonPath := filepath.Join(s.logsDir, fmt.Sprintf("jobs-%s.json", todayStr))
	txtPath := filepath.Join(s.logsDir, fmt.Sprintf("jobs-%s.txt", todayStr))

	var existingDaily []model.Job
	if data, err := os.ReadFile(jsonPath); err == nil {
		_ = json.Unmarshal(data, &existingDaily)
	}

	existingMap := make(map[string]bool)
	for _, j := range existingDaily {
		if j.ID != "" {
			existingMap[j.ID] = true
		}
	}

	var uniqueAdditions []model.Job
	for _, j := range jobs {
		if j.ID != "" && !existingMap[j.ID] {
			existingMap[j.ID] = true
			uniqueAdditions = append(uniqueAdditions, j)
		}
	}

	if len(uniqueAdditions) > 0 {
		combined := append(existingDaily, uniqueAdditions...)
		if data, err := json.MarshalIndent(combined, "", "  "); err == nil {
			_ = os.WriteFile(jsonPath, data, 0644)
		}
	}

	var lines []string
	for _, j := range uniqueAdditions {
		title := j.Title
		company := j.Company
		source := j.Source
		location := j.Location
		url := j.URL
		salary := "Not disclosed"
		if j.Salary != nil {
			salary = *j.Salary
		}
		lines = append(lines, fmt.Sprintf("[%s] %s | %s | %s | Gaji: %s\nURL: %s\n", source, title, company, location, salary, url))
	}

	if len(lines) > 0 {
		f, err := os.OpenFile(txtPath, os.O_APPEND|os.O_CREATE|os.O_WRONLY, 0644)
		if err == nil {
			defer f.Close()
			_, _ = f.WriteString(strings.Join(lines, "\n") + "\n")
		}
	}
}

func (s *StorageService) GetStatsCounts() (int, map[string]int, error) {
	s.mu.Lock()
	defer s.mu.Unlock()

	var total int
	if err := s.db.QueryRow("SELECT COUNT(*) FROM jobs").Scan(&total); err != nil {
		return 0, nil, err
	}

	rows, err := s.db.Query("SELECT source, COUNT(*) FROM jobs GROUP BY source")
	if err != nil {
		return total, nil, err
	}
	defer rows.Close()

	counts := make(map[string]int)
	for rows.Next() {
		var src string
		var c int
		if err := rows.Scan(&src, &c); err == nil {
			counts[src] = c
		}
	}
	return total, counts, nil
}
