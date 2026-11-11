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
		source := job.Source
		rawID := job.ID
		if rawID == "" {
			rawID = job.RawID
		}
		if rawID == "" {
			rawID = job.URL
		}
		if rawID == "" {
			rawID = job.Title
		}

		jobID := job.ID
		if jobID == "" {
			jobID = utils.GenerateJobID(source, rawID)
			job.ID = jobID
		}

		if !seenIDs[jobID] {
			seenIDs[jobID] = true
			newJobs = append(newJobs, *job)
			newIDs = append(newIDs, jobID)
		}
	}

	return newJobs, newIDs
}
