package engine

import (
	"fmt"
	"regexp"
	"strings"

	"lokerscraper-surabaya/internal/config"
	"lokerscraper-surabaya/internal/model"
)

var (
	keywordsRe  *regexp.Regexp
	locationsRe *regexp.Regexp
)

func InitFilter(cfg *config.Config) {
	if len(cfg.Keywords) > 0 {
		var parts []string
		for _, kw := range cfg.Keywords {
			q := regexp.QuoteMeta(kw)
			if len(kw) <= 3 {
				parts = append(parts, `\b`+q+`\b`)
			} else {
				parts = append(parts, q)
			}
		}
		pattern := fmt.Sprintf(`(?i)(?:%s)`, strings.Join(parts, "|"))
		keywordsRe = regexp.MustCompile(pattern)
	}

	if len(cfg.Locations) > 0 {
		var escaped []string
		for _, loc := range cfg.Locations {
			escaped = append(escaped, regexp.QuoteMeta(loc))
		}
		pattern := fmt.Sprintf(`(?i)\b(?:%s)\b`, strings.Join(escaped, "|"))
		locationsRe = regexp.MustCompile(pattern)
	}
}

func MatchesKeywords(job model.Job) bool {
	if keywordsRe == nil {
		return true
	}
	return keywordsRe.MatchString(job.Title)
}

func IsValidLocation(job model.Job) bool {
	if locationsRe == nil {
		return true
	}
	text := fmt.Sprintf("%s %s %s", job.Location, job.Title, job.WorkMode)
	return locationsRe.MatchString(text)
}

func FilterJobs(jobs []model.Job) []model.Job {
	var filtered []model.Job
	for _, j := range jobs {
		if MatchesKeywords(j) && IsValidLocation(j) {
			filtered = append(filtered, j)
		}
	}
	return filtered
}
