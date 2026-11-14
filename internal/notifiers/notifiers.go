package notifiers

import (
	"fmt"
	"net/http"
	"strings"
	"time"

	"lokerscraper-surabaya/internal/config"
	"lokerscraper-surabaya/internal/model"
)

var notifyHTTPClient = &http.Client{
	Timeout: 10 * time.Second,
}

func getDiscordWebhookURLs(cfg *config.Config) []string {
	var urls []string
	for _, u := range cfg.DiscordWebhookURLs {
		if u != "" {
			urls = append(urls, u)
		}
	}
	if len(urls) == 0 && cfg.DiscordWebhookURL != "" {
		urls = append(urls, cfg.DiscordWebhookURL)
	}

	seen := make(map[string]bool)
	var unique []string
	for _, u := range urls {
		if !seen[u] {
			seen[u] = true
			unique = append(unique, u)
		}
	}
	return unique
}

func NotifyNewJobs(cfg *config.Config, jobs []model.Job) {
	if len(jobs) == 0 {
		return
	}

	for _, webhookURL := range getDiscordWebhookURLs(cfg) {
		SendDiscordJobs(webhookURL, jobs)
	}

	botToken := strings.TrimSpace(cfg.TelegramBotToken)
	chatID := strings.TrimSpace(cfg.TelegramChatID)
	if botToken != "" && chatID != "" && !strings.Contains(botToken, "placeholder") && !strings.Contains(botToken, "your_") {
		SendTelegramJobs(botToken, chatID, jobs)
	}
}

func NotifyScraperError(cfg *config.Config, errors []string) {
	if len(errors) == 0 {
		return
	}

	nowStr := time.Now().UTC().Format("2006-01-02 15:04:05 UTC")
	var formattedErrs []string
	for _, err := range errors {
		formattedErrs = append(formattedErrs, fmt.Sprintf("• **%s**", err))
	}
	desc := fmt.Sprintf("Platform scraper berikut gagal **>= 3 siklus berturut-turut**:\n\n%s", strings.Join(formattedErrs, "\n"))

	webhookURLs := getDiscordWebhookURLs(cfg)
	if cfg.DiscordErrorWebhookURL != "" {
		webhookURLs = []string{cfg.DiscordErrorWebhookURL}
	}

	for _, u := range webhookURLs {
		payload := DiscordPayload{
			Embeds: []DiscordEmbed{
				{
					Title:       "🚨 Scraper Consecutive Failure Alert",
					Description: desc,
					Color:       0xE74C3C,
					Footer:      &DiscordFooter{Text: fmt.Sprintf("LokerScraper Surabaya • System Alert • %s", nowStr)},
				},
			},
		}
		SendDiscordPayload(u, payload)
	}

	botToken := strings.TrimSpace(cfg.TelegramBotToken)
	chatID := strings.TrimSpace(cfg.TelegramErrorChatID)
	if chatID == "" {
		chatID = strings.TrimSpace(cfg.TelegramChatID)
	}
	if botToken != "" && chatID != "" && !strings.Contains(botToken, "placeholder") && !strings.Contains(botToken, "your_") {
		text := fmt.Sprintf("🚨 <b>Scraper Failure Alert</b>\n\n%s\n\n<i>%s</i>", desc, nowStr)
		SendTelegramMessage(botToken, chatID, text)
	}
}
