package model

type Job struct {
	ID                  string      `json:"id,omitempty"`
	RawID               string      `json:"raw_id,omitempty"`
	Source              string      `json:"source,omitempty"`
	Title               string      `json:"title,omitempty"`
	Company             string      `json:"company,omitempty"`
	LogoURL             *string     `json:"logo_url,omitempty"`
	CompanyIndustry     *string     `json:"company_industry,omitempty"`
	CompanyDescription  *string     `json:"company_description,omitempty"`
	Location            string      `json:"location,omitempty"`
	SalaryMin           *int        `json:"salary_min,omitempty"`
	SalaryMax           *int        `json:"salary_max,omitempty"`
	SalaryCurrency      *string     `json:"salary_currency,omitempty"`
	WorkType            *string     `json:"work_type,omitempty"`
	WorkMode            string      `json:"work_mode,omitempty"`
	PostedAt            string      `json:"posted_at,omitempty"`
	ApplicationDeadline *string     `json:"application_deadline,omitempty"`
	ApplicantCount      *int        `json:"applicant_count,omitempty"`
	NumberOfOpenings    *int        `json:"number_of_openings,omitempty"`
	Skills              []string    `json:"skills,omitempty"`
	Experience          *string     `json:"experience,omitempty"`
	Education           *string     `json:"education,omitempty"`
	JobDescription      *string     `json:"job_description,omitempty"`
	Qualifications      *string     `json:"qualifications,omitempty"`
	Benefits            []string    `json:"benefits,omitempty"`
	URL                 string      `json:"url,omitempty"`
	ScrapedAt           string      `json:"scraped_at,omitempty"`
	Salary              *string     `json:"salary,omitempty"`
}
