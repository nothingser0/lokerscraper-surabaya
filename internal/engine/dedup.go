package engine

import (
	"lokerscraper-surabaya/internal/model"
	"lokerscraper-surabaya/internal/utils"
)

func GenerateJobID(source, rawIdentifier string) string {
	return utils.GenerateJobID(source, rawIdentifier)
}

func DeduplicateJobs(jobs []model.Job, seenIDs map[string]bool) ([]model.Job, []string) {
	var newJobs []model.Job
	var newIDs []string

	for i := range jobs {
		job := &jobs[i]
		if job.Source == "" {
			job.Source = "Unknown"
		}
		rawID := job.RawID
		if rawID == "" {
			rawID = job.URL
		}
		if rawID == "" {
			rawID = job.Title
		}

		jobID := job.ID
		if jobID == "" {
			jobID = utils.GenerateJobID(job.Source, rawID)
			job.ID = jobID
		}

		sigID := utils.GenerateContentSignature(job.Title, job.Company, job.Location)

		if seenIDs[jobID] || (sigID != "" && seenIDs[sigID]) {
			continue
		}

		seenIDs[jobID] = true
		newIDs = append(newIDs, jobID)
		if sigID != "" {
			seenIDs[sigID] = true
			newIDs = append(newIDs, sigID)
		}
		newJobs = append(newJobs, *job)
	}

	return newJobs, newIDs
}
