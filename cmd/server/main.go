package main

import (
	"context"
	"io"
	"log"
	"net/http"
	"os"
	"os/signal"
	"syscall"
	"time"

	"lokerscraper-surabaya/internal/api"
	"lokerscraper-surabaya/internal/config"
	"lokerscraper-surabaya/internal/engine"
	"lokerscraper-surabaya/internal/storage"
)

func main() {
	cfg := config.LoadConfig()

	_ = os.MkdirAll(cfg.LogsDir, 0755)
	logFile, err := os.OpenFile(cfg.LogFile, os.O_CREATE|os.O_WRONLY|os.O_APPEND, 0644)
	if err == nil {
		defer logFile.Close()
		multi := io.MultiWriter(os.Stdout, logFile)
		log.SetOutput(multi)
	} else {
		log.SetOutput(os.Stdout)
	}
	log.SetFlags(log.Ldate | log.Ltime | log.Lshortfile)

	log.Printf("[Main] Starting LokerScraper Surabaya (Golang Ultra-Low RAM Edition)...")
	log.Printf("[Main] Base directory: %s", cfg.BaseDir)
	log.Printf("[Main] Data directory: %s", cfg.DataDir)

	engine.InitFilter(cfg)

	store, err := storage.NewStorageService(cfg)
	if err != nil {
		log.Fatalf("[Main] Failed to initialize storage: %v", err)
	}
	defer store.Close()

	runner := engine.NewRunner(cfg, store)
	server := api.NewServer(cfg, store, runner)

	mux := http.NewServeMux()
	server.RegisterRoutes(mux)

	// Scheduled background scrape
	stopSched := make(chan struct{})
	go func() {
		// First scheduled run after 1 minute (same as Python APScheduler next_run_time)
		initialTimer := time.NewTimer(1 * time.Minute)
		select {
		case <-initialTimer.C:
			log.Println("[Scheduler] Triggering initial scrape cycle...")
			res, err := runner.RunCycle(false)
			server.SetLastScrapedAt(time.Now().UTC().Format(time.RFC3339))
			if err != nil {
				log.Printf("[Scheduler] Error in initial scrape: %v", err)
			} else {
				log.Printf("[Scheduler] Initial scrape finished: %d new jobs.", res.NewJobsCount)
			}
		case <-stopSched:
			initialTimer.Stop()
			return
		}

		interval := cfg.RandomScrapeInterval()
		ticker := time.NewTicker(interval)
		defer ticker.Stop()

		for {
			select {
			case <-ticker.C:
				log.Println("[Scheduler] Triggering periodic scrape cycle...")
				res, err := runner.RunCycle(false)
				server.SetLastScrapedAt(time.Now().UTC().Format(time.RFC3339))
				if err != nil {
					log.Printf("[Scheduler] Error in scheduled scrape: %v", err)
				} else {
					log.Printf("[Scheduler] Scheduled scrape finished: %d new jobs.", res.NewJobsCount)
				}
				// Re-evaluate interval if random interval range configured
				ticker.Reset(cfg.RandomScrapeInterval())
			case <-stopSched:
				return
			}
		}
	}()

	port := os.Getenv("PORT")
	if port == "" {
		port = "5000"
	}
	addr := "0.0.0.0:" + port

	httpServer := &http.Server{
		Addr:              addr,
		Handler:           mux,
		ReadHeaderTimeout: 10 * time.Second,
		IdleTimeout:       60 * time.Second,
	}

	sigChan := make(chan os.Signal, 1)
	signal.Notify(sigChan, os.Interrupt, syscall.SIGTERM)

	go func() {
		log.Printf("[Main] Server listening on http://%s", addr)
		if err := httpServer.ListenAndServe(); err != nil && err != http.ErrServerClosed {
			log.Fatalf("[Main] Server error: %v", err)
		}
	}()

	sig := <-sigChan
	log.Printf("[Main] Received signal %v. Initiating graceful shutdown...", sig)
	close(stopSched)

	ctx, cancel := context.WithTimeout(context.Background(), 10*time.Second)
	defer cancel()

	if err := httpServer.Shutdown(ctx); err != nil {
		log.Printf("[Main] Server shutdown error: %v", err)
	}

	log.Println("[Main] Application exited gracefully.")
}
