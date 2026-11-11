package config

import (
	"math/rand"
	"os"
	"path/filepath"
	"strconv"
	"strings"
	"time"

	"github.com/joho/godotenv"
)

type Config struct {
	DiscordWebhookURL      string
	DiscordWebhookURLs     []string
	DiscordErrorWebhookURL string
	TelegramBotToken       string
	TelegramChatID         string
	TelegramErrorChatID    string
	DeepLAPIKey            string
	DeepLAPIURL            string
	ScrapeIntervalHours    int
	ScrapeIntervalMinHours int
	ScrapeIntervalMaxHours int
	TriggerToken           string
	JobRetentionDays       int
	Keywords               []string
	Locations              []string
	MaxWorkers             int

	BaseDir  string
	DataDir  string
	LogsDir  string
	LogFile  string
	StaticDir string
}

var AppConfig *Config

const (
	defaultKeywords  = "developer,engineer,programmer,backend,frontend,fullstack,mobile,data,devops,qa,tester,web,quality assurance,software"
	defaultLocations = "surabaya,sidoarjo,gresik,remote"
)

func LoadConfig() *Config {
	baseDir, err := os.Getwd()
	if err != nil {
		baseDir = "."
	}

	_ = godotenv.Overload(filepath.Join(baseDir, ".env"))

	dataDir := filepath.Join(baseDir, "data")
	logsDir := filepath.Join(baseDir, "logs")
	staticDir := filepath.Join(baseDir, "static")

	_ = os.MkdirAll(dataDir, 0755)
	_ = os.MkdirAll(logsDir, 0755)

	getInt := func(key string, def int) int {
		val := os.Getenv(key)
		if val == "" {
			return def
		}
		i, err := strconv.Atoi(strings.TrimSpace(val))
		if err != nil {
			return def
		}
		return i
	}

	rawUrls := os.Getenv("DISCORD_WEBHOOK_URLS")
	var webhookUrls []string
	if rawUrls != "" {
		for _, u := range strings.Split(rawUrls, ",") {
			trimmed := strings.TrimSpace(u)
			if trimmed != "" {
				webhookUrls = append(webhookUrls, trimmed)
			}
		}
	}

	splitList := func(raw string) []string {
		var list []string
		for _, item := range strings.Split(raw, ",") {
			t := strings.ToLower(strings.TrimSpace(item))
			if t != "" {
				list = append(list, t)
			}
		}
		return list
	}

	kwRaw := os.Getenv("KEYWORDS")
	if kwRaw == "" {
		kwRaw = defaultKeywords
	}

	locRaw := os.Getenv("LOCATIONS")
	if locRaw == "" {
		locRaw = defaultLocations
	}

	maxWorkers := getInt("MAX_WORKERS", 2)
	if maxWorkers <= 0 {
		maxWorkers = 2
	}

	cfg := &Config{
		DiscordWebhookURL:      os.Getenv("DISCORD_WEBHOOK_URL"),
		DiscordWebhookURLs:     webhookUrls,
		DiscordErrorWebhookURL: os.Getenv("DISCORD_ERROR_WEBHOOK_URL"),
		TelegramBotToken:       os.Getenv("TELEGRAM_BOT_TOKEN"),
		TelegramChatID:         os.Getenv("TELEGRAM_CHAT_ID"),
		TelegramErrorChatID:    os.Getenv("TELEGRAM_ERROR_CHAT_ID"),
		DeepLAPIKey:            os.Getenv("DEEPL_API_KEY"),
		DeepLAPIURL:            os.Getenv("DEEPL_API_URL"),
		ScrapeIntervalHours:    getInt("SCRAPE_INTERVAL_HOURS", 6),
		ScrapeIntervalMinHours: getInt("SCRAPE_INTERVAL_MIN_HOURS", 0),
		ScrapeIntervalMaxHours: getInt("SCRAPE_INTERVAL_MAX_HOURS", 0),
		TriggerToken:           os.Getenv("TRIGGER_TOKEN"),
		JobRetentionDays:       getInt("JOB_RETENTION_DAYS", 30),
		Keywords:               splitList(kwRaw),
		Locations:              splitList(locRaw),
		MaxWorkers:             maxWorkers,

		BaseDir:   baseDir,
		DataDir:   dataDir,
		LogsDir:   logsDir,
		LogFile:   filepath.Join(logsDir, "scraper.log"),
		StaticDir: staticDir,
	}

	if cfg.DeepLAPIURL == "" {
		cfg.DeepLAPIURL = "https://api-free.deepl.com/v2/translate"
	}

	AppConfig = cfg
	return cfg
}

func (c *Config) RandomScrapeInterval() time.Duration {
	lo := c.ScrapeIntervalMinHours
	hi := c.ScrapeIntervalMaxHours
	if lo > 0 && hi > lo {
		r := rand.Intn(hi-lo+1) + lo
		return time.Duration(r) * time.Hour
	}
	return time.Duration(c.ScrapeIntervalHours) * time.Hour
}
