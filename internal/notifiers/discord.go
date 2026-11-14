package notifiers

import (
	"bytes"
	"encoding/json"
	"fmt"
	"log"
	"strings"
	"time"

	"lokerscraper-surabaya/internal/model"
	"lokerscraper-surabaya/internal/utils"
)

var colorMap = map[string]int{
	"kalibrr":    0x00A8FF,
	"jobstreet":  0x6C5CE7,
	"glints":     0xFF7675,
	"linkedin":   0x0A66C2,
	"sejutacita": 0x00B894,
	"techinasia": 0xE67E22,
	"remoteok":   0xFF4742,
	"karir":      0x1ABC9C,
}

var sourceEmoji = map[string]string{
	"kalibrr":    "🟦",
	"jobstreet":  "🟪",
	"glints":     "🟥",
	"linkedin":   "🔷",
	"sejutacita": "🟩",
	"techinasia": "🟧",
	"remoteok":   "🔴",
	"karir":      "🟢",
}

type DiscordField struct {
	Name   string `json:"name"`
	Value  string `json:"value"`
	Inline bool   `json:"inline"`
}

type DiscordAuthor struct {
	Name string `json:"name"`
}

type DiscordFooter struct {
	Text string `json:"text"`
}

type DiscordThumbnail struct {
	URL string `json:"url"`
}

type DiscordEmbed struct {
	Title       string            `json:"title"`
	URL         string            `json:"url,omitempty"`
	Color       int               `json:"color"`
	Author      *DiscordAuthor    `json:"author,omitempty"`
	Description string            `json:"description,omitempty"`
	Fields      []DiscordField    `json:"fields,omitempty"`
	Thumbnail   *DiscordThumbnail `json:"thumbnail,omitempty"`
	Footer      *DiscordFooter    `json:"footer,omitempty"`
}

type DiscordPayload struct {
	Embeds []DiscordEmbed `json:"embeds"`
}

func clip(value string, maxLen int) string {
	val := strings.TrimSpace(value)
	if len(val) <= maxLen {
		return val
	}
	return strings.TrimRight(val[:maxLen-1], " ") + "…"
}

func JobToDiscordEmbed(job model.Job) DiscordEmbed {
	sourceLower := strings.ToLower(job.Source)
	color, ok := colorMap[sourceLower]
	if !ok {
		color = 0x7289DA
	}
	emoji, ok := sourceEmoji[sourceLower]
	if !ok {
		emoji = "🔹"
	}

	title := job.Title
	if title == "" {
		title = "No Title"
	}

	company := job.Company
	if company == "" {
		company = "Unknown"
	}

	location := job.Location
	if location == "" {
		location = "N/A"
	}

	salary := "Not disclosed"
	if job.Salary != nil && *job.Salary != "" {
		salary = utils.FormatSalary(*job.Salary)
	} else if job.SalaryMin != nil || job.SalaryMax != nil {
		sMin := ""
		if job.SalaryMin != nil {
			sMin = fmt.Sprintf("%d", *job.SalaryMin)
		}
		sMax := ""
		if job.SalaryMax != nil {
			sMax = fmt.Sprintf("%d", *job.SalaryMax)
		}
		salary = utils.FormatSalary(fmt.Sprintf("%s - %s", sMin, sMax))
	}

	workMode := utils.FormatWorkMode(job.WorkMode)
	workType := "N/A"
	if job.WorkType != nil {
		workType = utils.FormatJobType(*job.WorkType)
	}
	postedAt := utils.FormatDate(job.PostedAt)

	fields := []DiscordField{
		{Name: "Perusahaan", Value: clip(company, 28), Inline: true},
		{Name: "Gaji", Value: clip(salary, 28), Inline: true},
		{Name: "Tgl", Value: clip(postedAt, 28), Inline: true},
		{Name: "Lokasi", Value: clip(location, 28), Inline: true},
		{Name: "Tipe", Value: clip(workType, 28), Inline: true},
		{Name: "Mode", Value: clip(workMode, 28), Inline: true},
	}

	if job.CompanyIndustry != nil && *job.CompanyIndustry != "" {
		fields = append(fields, DiscordField{Name: "Industri", Value: clip(*job.CompanyIndustry, 200), Inline: true})
	}
	if job.Experience != nil && *job.Experience != "" {
		fields = append(fields, DiscordField{Name: "Pengalaman", Value: clip(utils.FormatExperience(*job.Experience), 28), Inline: true})
	}
	if job.Education != nil && *job.Education != "" {
		fields = append(fields, DiscordField{Name: "Pendidikan", Value: clip(*job.Education, 28), Inline: true})
	}
	if job.ApplicationDeadline != nil && *job.ApplicationDeadline != "" {
		fields = append(fields, DiscordField{Name: "Batas Lamaran", Value: clip(utils.FormatDate(*job.ApplicationDeadline), 28), Inline: true})
	}
	if job.ApplicantCount != nil {
		fields = append(fields, DiscordField{Name: "Pelamar", Value: fmt.Sprintf("%d", *job.ApplicantCount), Inline: true})
	}
	if job.NumberOfOpenings != nil {
		fields = append(fields, DiscordField{Name: "Kuota", Value: fmt.Sprintf("%d", *job.NumberOfOpenings), Inline: true})
	}
	if len(job.Skills) > 0 {
		fields = append(fields, DiscordField{Name: "Skills", Value: clip(strings.Join(job.Skills, ", "), 300), Inline: false})
	}
	if len(job.Benefits) > 0 {
		fields = append(fields, DiscordField{Name: "Fasilitas", Value: clip(strings.Join(job.Benefits, ", "), 300), Inline: false})
	}
	if job.JobDescription != nil && *job.JobDescription != "" {
		fields = append(fields, DiscordField{Name: "Deskripsi", Value: utils.FormatDescription(*job.JobDescription, 700), Inline: false})
	}

	embed := DiscordEmbed{
		Title:  title,
		URL:    job.URL,
		Color:  color,
		Author: &DiscordAuthor{Name: fmt.Sprintf("%s %s", emoji, job.Source)},
		Fields: fields,
		Footer: &DiscordFooter{Text: "LokerScraper Surabaya"},
	}

	if job.LogoURL != nil && strings.HasPrefix(*job.LogoURL, "http") {
		embed.Thumbnail = &DiscordThumbnail{URL: *job.LogoURL}
	}

	return embed
}

func SendDiscordPayload(webhookURL string, payload DiscordPayload) bool {
	data, err := json.Marshal(payload)
	if err != nil {
		return false
	}

	retries := 0
	backoff := 1 * time.Second
	for retries <= 3 {
		resp, err := notifyHTTPClient.Post(webhookURL, "application/json", bytes.NewBuffer(data))
		if err != nil {
			log.Printf("[Discord] Request error: %v", err)
			time.Sleep(backoff)
			retries++
			backoff *= 2
			continue
		}
		resp.Body.Close()

		if resp.StatusCode == 200 || resp.StatusCode == 204 {
			return true
		} else if resp.StatusCode == 429 {
			log.Printf("[Discord] Rate limited (429). Retrying after %v...", backoff)
			time.Sleep(backoff)
			retries++
			backoff *= 2
		} else {
			log.Printf("[Discord] Webhook returned status: %d", resp.StatusCode)
			return false
		}
	}
	return false
}

func SendDiscordJobs(webhookURL string, jobs []model.Job) bool {
	if webhookURL == "" || len(jobs) == 0 {
		return false
	}

	batchSize := 3
	for i := 0; i < len(jobs); i += batchSize {
		end := i + batchSize
		if end > len(jobs) {
			end = len(jobs)
		}

		var embeds []DiscordEmbed
		for _, j := range jobs[i:end] {
			embeds = append(embeds, JobToDiscordEmbed(j))
		}

		payload := DiscordPayload{Embeds: embeds}
		SendDiscordPayload(webhookURL, payload)
		if end < len(jobs) {
			time.Sleep(1200 * time.Millisecond)
		}
	}
	return true
}
