package notifiers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"html"
	"log"
	"net/http"
	"time"

	"lokerscraper-surabaya/internal/model"
)

type TelegramMessage struct {
	ChatID                string `json:"chat_id"`
	Text                  string `json:"text"`
	ParseMode             string `json:"parse_mode"`
	DisableWebPagePreview bool   `json:"disable_web_page_preview"`
}

func FormatTelegramJob(job model.Job) string {
	title := html.EscapeString(job.Title)
	company := html.EscapeString(job.Company)
	location := html.EscapeString(job.Location)
	workMode := html.EscapeString(job.WorkMode)
	source := html.EscapeString(job.Source)
	url := job.URL

	msg := fmt.Sprintf(
		"<b>%s</b>\n🏢 <b>Company:</b> %s\n📍 <b>Location:</b> %s\n💼 <b>Mode:</b> %s\n🌐 <b>Source:</b> %s\n",
		title, company, location, workMode, source,
	)
	if url != "" {
		msg += fmt.Sprintf("🔗 <a href=\"%s\">Apply Here</a>", html.EscapeString(url))
	}
	return msg
}

func SendTelegramMessage(botToken, chatID, text string) bool {
	url := fmt.Sprintf("https://api.telegram.org/bot%s/sendMessage", botToken)
	payload := TelegramMessage{
		ChatID:                chatID,
		Text:                  text,
		ParseMode:             "HTML",
		DisableWebPagePreview: true,
	}

	data, err := json.Marshal(payload)
	if err != nil {
		return false
	}

	client := &http.Client{Timeout: 10 * time.Second}
	retries := 0
	backoff := 1 * time.Second
	for retries <= 3 {
		resp, err := client.Post(url, "application/json", bytes.NewBuffer(data))
		if err != nil {
			log.Printf("[Telegram] Request error: %v", err)
			time.Sleep(backoff)
			retries++
			backoff *= 2
			continue
		}
		defer resp.Body.Close()

		if resp.StatusCode == 200 {
			return true
		} else if resp.StatusCode == 429 {
			time.Sleep(backoff)
			retries++
			backoff *= 2
		} else {
			log.Printf("[Telegram] Send failed with status: %d", resp.StatusCode)
			return false
		}
	}
	return false
}

func SendTelegramJobs(botToken, chatID string, jobs []model.Job) bool {
	if botToken == "" || chatID == "" || len(jobs) == 0 {
		return false
	}

	for _, j := range jobs {
		text := FormatTelegramJob(j)
		SendTelegramMessage(botToken, chatID, text)
		time.Sleep(50 * time.Millisecond)
	}
	return true
}
