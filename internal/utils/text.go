package utils

import (
	"crypto/md5"
	"encoding/hex"
	"fmt"
	"html"
	"regexp"
	"strconv"
	"strings"
	"time"
	"unicode"

	"golang.org/x/text/unicode/norm"
)

var (
	tagRe          = regexp.MustCompile(`<[^>]+>`)
	ctrlRe         = regexp.MustCompile(`[\x00-\x1f\x7f-\x9f]`)
	descCtrlRe     = regexp.MustCompile(`[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]`)
	wsRe           = regexp.MustCompile(`\s+`)
	salPrefixRe    = regexp.MustCompile(`(?i)^(?:idr|rp|usd|sgd|eur)\s*`)
	salSuffixRe    = regexp.MustCompile(`(?i)\s*(?:per|/)?\s*(month|bulan|year|tahun|day|hari)\b.*$`)
	salMilRe       = regexp.MustCompile(`(?i)^(\d+(?:\.\d+)?)\s*(m|jt|juta|million|mil)$`)
	salKRe         = regexp.MustCompile(`(?i)^(\d+(?:\.\d+)?)\s*(k|rb|ribu|thousand)$`)
	salSplitRe     = regexp.MustCompile(`\s*[-–—~|]\s*`)
	descLineRe     = regexp.MustCompile(`(?i)<br\s*/?>|</p>|</h\d>|</div>|</ul>|</ol>|<button[^>]*>|</button>`)
	descLiRe       = regexp.MustCompile(`(?i)<li[^>]*>`)
	descUlRe       = regexp.MustCompile(`(?i)<ul[^>]*>|<ol[^>]*>`)
	salRangeRe     = regexp.MustCompile(`(?i)(\d+)\s*(?:–|-|to|s/d)\s*(\d+)`)
	salNumRe       = regexp.MustCompile(`\b\d+\b`)
	nonAlphaNumRe  = regexp.MustCompile(`[^a-z0-9]+`)
)

var weekdaysID = []string{
	"Minggu", "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu",
}

var monthsID = []string{
	"Januari", "Februari", "Maret", "April", "Mei", "Juni",
	"Juli", "Agustus", "September", "Oktober", "November", "Desember",
}

var kalibrrExpMap = map[int]string{
	200: "1-3 tahun",
	400: "5+ tahun",
}

var kalibrrEduMap = map[int]string{
	200: "SMA/SMK",
	550: "D3/S1 (Diploma/Sarjana)",
}

var glintsEduMap = map[string]string{
	"BACHELOR":    "S1",
	"DIPLOMA":     "D1-D4",
	"HIGH_SCHOOL": "SMA/SMK",
	"MASTER":      "S2",
}

var experienceLevelMap = map[string]string{
	"internship":        "Magang",
	"entry level":       "Level Pemula",
	"associate":         "Level Asosiat",
	"mid-senior level":  "Level Menengah-Senior",
	"director":          "Direktur",
	"executive":         "Eksekutif",
	"not applicable":    "",
	"":                  "",
}

var jobTypeMap = map[string]string{
	"full_time":      "Penuh Waktu",
	"fulltime":       "Penuh Waktu",
	"full time":      "Penuh Waktu",
	"full-time":      "Penuh Waktu",
	"permanent":      "Tetap",
	"part_time":      "Paruh Waktu",
	"parttime":       "Paruh Waktu",
	"part time":      "Paruh Waktu",
	"part-time":      "Paruh Waktu",
	"contract":       "Kontrak",
	"contract/temp":  "Kontrak/Sementara",
	"contract temp":  "Kontrak/Sementara",
	"temporary":      "Sementara",
	"temp":           "Sementara",
	"internship":     "Magang",
	"intern":         "Magang",
	"project_based":  "Berbasis Proyek",
	"project based":  "Berbasis Proyek",
	"project-based":  "Berbasis Proyek",
	"freelance":      "Freelance",
	"remote":         "Remote",
	"hybrid":         "Hybrid",
	"onsite":         "On-site",
	"on_site":        "On-site",
}

var benefitMap = map[string]string{
	"car":                          "Mobil Dinas",
	"child_care":                   "Fasilitas Penitipan Anak",
	"family_leave":                 "Cuti Keluarga",
	"flexitime":                    "Jam Kerja Fleksibel",
	"life_ins":                     "Asuransi Jiwa",
	"mat_pat_leave":                "Cuti Melahirkan/Ayah",
	"med_ins":                      "Asuransi Kesehatan",
	"med_plans":                    "Paket Kesehatan",
	"paid_holidays":                "Libur Berbayar",
	"perf_bonus":                   "Bonus Kinerja",
	"sick_leave":                   "Izin Sakit",
	"single_leave":                 "Cuti Lajang",
	"special_for_women":            "Fasilitas Khusus Wanita",
	"trans":                        "Tunjangan Transportasi",
	"wfh":                          "Bisa Kerja dari Rumah",
	"competitivesalary":            "Gaji Kompetitif",
	"bonussystem":                  "Sistem Bonus",
	"casualdresscode":              "Busana Santai",
	"maternityleave":               "Cuti Melahirkan",
	"paidsickdays":                 "Izin Sakit Berbayar",
	"professionaldevelopment":      "Pengembangan Profesional",
	"wellnessprogram":              "Program Kesehatan",
	"freemeals":                    "Makan Gratis",
	"teambuilding":                 "Kegiatan Team Building",
	"employeediscounts":            "Diskon Karyawan",
	"annual bonus":                 "Bonus Tahunan",
	"facility reimbursement":       "Reimbursement Fasilitas",
	"birthday treat":               "Hadiah Ulang Tahun",
	"companyoutings":               "Kegiatan Perusahaan (Company Outing)",
	"freelunch":                    "Makan Siang Gratis",
	"gymmembership":                "Keanggotaan Gym",
	"internationalexposure":        "Eksposur Internasional",
	"medicalleave":                 "Cuti Sakit (Medis)",
	"periodleave":                  "Cuti Haid",
	"selfdevelopmentallowance":     "Tunjangan Pengembangan Diri",
	"transport":                    "Tunjangan Transportasi",
	"vacationtime":                 "Waktu Libur",
	"early wages program":          "Program Gaji Awal",
	"flexible working environment": "Lingkungan Kerja Fleksibel",
	"health insurance":             "Asuransi Kesehatan",
	"personal loan":                "Pinjaman Karyawan",
	"sign on bonus":                "Bonus Tanda Tangan",
}

func SanitizeText(text string) string {
	if text == "" {
		return ""
	}
	text = html.UnescapeString(text)
	text = tagRe.ReplaceAllString(text, " ")
	text = string(norm.NFKC.Bytes([]byte(text)))
	text = ctrlRe.ReplaceAllString(text, "")
	text = wsRe.ReplaceAllString(text, " ")
	return strings.TrimSpace(text)
}

func FormatWorkMode(value string) string {
	val := strings.ToLower(SanitizeText(value))
	switch val {
	case "remote":
		return "Remote"
	case "hybrid":
		return "Hybrid"
	case "onsite", "on-site", "on site":
		return "On-site"
	}
	if value == "" {
		return "N/A"
	}
	s := SanitizeText(value)
	if s == "" {
		return "N/A"
	}
	return s
}

func FormatJobType(value string) string {
	if value == "" {
		return "N/A"
	}
	text := SanitizeText(value)
	if text == "" {
		return "N/A"
	}
	key := strings.ToLower(text)
	key = strings.ReplaceAll(key, "-", " ")
	key = strings.ReplaceAll(key, "_", " ")
	key = wsRe.ReplaceAllString(key, " ")
	key = strings.TrimSpace(key)
	if mapped, ok := jobTypeMap[key]; ok {
		return mapped
	}
	return text
}

func FormatExperience(value string) string {
	if value == "" {
		return "N/A"
	}
	text := SanitizeText(value)
	key := strings.ToLower(text)
	if mapped, ok := experienceLevelMap[key]; ok {
		if mapped == "" {
			return "N/A"
		}
		return mapped
	}
	return text
}

func DecodeKalibrrExperience(code interface{}) *string {
	if code == nil {
		return nil
	}
	var val int
	switch v := code.(type) {
	case int:
		val = v
	case float64:
		val = int(v)
	case string:
		i, err := strconv.Atoi(v)
		if err != nil {
			return nil
		}
		val = i
	default:
		return nil
	}
	if res, ok := kalibrrExpMap[val]; ok {
		return &res
	}
	return nil
}

func DecodeKalibrrEducation(code interface{}) *string {
	if code == nil {
		return nil
	}
	var val int
	switch v := code.(type) {
	case int:
		val = v
	case float64:
		val = int(v)
	case string:
		i, err := strconv.Atoi(v)
		if err != nil {
			return nil
		}
		val = i
	default:
		return nil
	}
	if res, ok := kalibrrEduMap[val]; ok {
		return &res
	}
	return nil
}

func DecodeGlintsEducation(code interface{}) *string {
	if code == nil {
		return nil
	}
	s := strings.ToUpper(fmt.Sprintf("%v", code))
	if res, ok := glintsEduMap[s]; ok {
		return &res
	}
	return nil
}

func DecodeBenefit(raw interface{}) *string {
	if raw == nil {
		return nil
	}
	text := strings.TrimSpace(fmt.Sprintf("%v", raw))
	if text == "" {
		return nil
	}
	key := strings.ToLower(strings.ReplaceAll(text, "-", "_"))
	if res, ok := benefitMap[key]; ok {
		return &res
	}
	return &text
}

func FormatDate(value string) string {
	if value == "" {
		return "N/A"
	}
	value = strings.TrimSpace(value)

	t, err := time.Parse(time.RFC3339, value)
	if err == nil {
		weekday := weekdaysID[int(t.Weekday())]
		month := monthsID[int(t.Month())-1]
		return fmt.Sprintf("%s, %d %s %d", weekday, t.Day(), month, t.Year())
	}

	t, err = time.Parse("2006-01-02", value)
	if err == nil {
		weekday := weekdaysID[int(t.Weekday())]
		month := monthsID[int(t.Month())-1]
		return fmt.Sprintf("%s, %d %s %d", weekday, t.Day(), month, t.Year())
	}

	return value
}

func FormatSalary(value string) string {
	if value == "" {
		return "Not disclosed"
	}
	text := SanitizeText(value)
	lower := strings.ToLower(text)
	if lower == "" || lower == "none" || lower == "null" || lower == "not disclosed" || lower == "competitive" || lower == "negotiable" {
		return "Not disclosed"
	}

	text = strings.ReplaceAll(text, "{", "")
	text = strings.ReplaceAll(text, "}", "")
	text = strings.ReplaceAll(text, "'", "")
	text = strings.ReplaceAll(text, "\"", "")

	compact := func(n float64) string {
		if n >= 1000000 {
			m := n / 1000000
			if m == float64(int(m)) {
				return fmt.Sprintf("Rp%djt", int(m))
			}
			return fmt.Sprintf("Rp%.1fjt", m)
		}
		if n >= 1000 {
			k := n / 1000
			if k == float64(int(k)) {
				return fmt.Sprintf("Rp%drb", int(k))
			}
			return fmt.Sprintf("Rp%.1frb", k)
		}
		return fmt.Sprintf("Rp%d", int(n))
	}

	parseAmount := func(tok string) string {
		tok = strings.TrimSpace(tok)
		tok = salPrefixRe.ReplaceAllString(tok, "")
		tok = strings.TrimSpace(salSuffixRe.ReplaceAllString(tok, ""))
		if tok == "" {
			return ""
		}

		if m := salMilRe.FindStringSubmatch(tok); len(m) > 1 {
			if f, err := strconv.ParseFloat(m[1], 64); err == nil {
				return compact(f * 1000000)
			}
		}

		if m := salKRe.FindStringSubmatch(tok); len(m) > 1 {
			if f, err := strconv.ParseFloat(m[1], 64); err == nil {
				return compact(f * 1000)
			}
		}

		bare := strings.ReplaceAll(strings.ReplaceAll(tok, ",", ""), ".", "")
		if f, err := strconv.ParseFloat(bare, 64); err == nil {
			return compact(f)
		}
		return tok
	}

	tokens := salSplitRe.Split(text, -1)

	var unique []string
	seen := make(map[string]bool)
	for _, tok := range tokens {
		t := strings.TrimSpace(tok)
		if t == "" || strings.EqualFold(t, "up to") || strings.EqualFold(t, "from") {
			continue
		}
		p := parseAmount(t)
		if p != "" && !seen[p] {
			seen[p] = true
			unique = append(unique, p)
		}
	}

	if len(unique) == 0 {
		return "Not disclosed"
	}
	return strings.Join(unique, " - ")
}

func CleanDescription(text string) string {
	if text == "" {
		return ""
	}
	text = html.UnescapeString(text)
	text = descLineRe.ReplaceAllString(text, "\n")
	text = descLiRe.ReplaceAllString(text, "\n• ")
	text = descUlRe.ReplaceAllString(text, "\n")
	text = tagRe.ReplaceAllString(text, " ")
	text = string(norm.NFKC.Bytes([]byte(text)))
	text = descCtrlRe.ReplaceAllString(text, "")

	lines := strings.Split(text, "\n")
	var out []string
	for _, ln := range lines {
		trimmed := wsRe.ReplaceAllString(strings.TrimSpace(ln), " ")
		if trimmed != "" {
			low := strings.ToLower(trimmed)
			if low != "show more" && low != "show less" {
				out = append(out, trimmed)
			}
		} else if len(out) > 0 && out[len(out)-1] != "" {
			out = append(out, "")
		}
	}
	return strings.TrimSpace(strings.Join(out, "\n"))
}

func DraftJSToText(raw interface{}) *string {
	m, ok := raw.(map[string]interface{})
	if !ok {
		return nil
	}
	blocks, ok := m["blocks"].([]interface{})
	if !ok || len(blocks) == 0 {
		return nil
	}

	var lines []string
	for _, b := range blocks {
		block, ok := b.(map[string]interface{})
		if !ok {
			continue
		}
		text, _ := block["text"].(string)
		text = strings.TrimSpace(text)
		btype, _ := block["type"].(string)
		btype = strings.ToLower(btype)

		if btype == "unordered-list-item" || btype == "ordered-list-item" {
			if text != "" {
				lines = append(lines, "• "+text)
			}
		} else if strings.HasPrefix(btype, "header") {
			if text != "" {
				lines = append(lines, text, "")
			}
		} else {
			if text != "" {
				lines = append(lines, text, "")
			}
		}
	}

	for len(lines) > 0 && lines[len(lines)-1] == "" {
		lines = lines[:len(lines)-1]
	}

	res := strings.TrimSpace(strings.Join(lines, "\n"))
	if res == "" {
		return nil
	}
	return &res
}

func FormatDescription(desc string, maxLen int) string {
	cleaned := CleanDescription(desc)
	if cleaned == "" {
		return ""
	}
	if len(cleaned) <= maxLen {
		return cleaned
	}
	cut := cleaned[:maxLen]
	if idx := strings.LastIndex(cut, "\n"); idx != -1 {
		cut = cut[:idx]
	}
	return strings.TrimRightFunc(cut, unicode.IsSpace) + "…"
}

func ParseSalaryLabel(label string) (*int, *int) {
	if label == "" {
		return nil, nil
	}
	clean := strings.ReplaceAll(label, "Rp", "")
	clean = strings.ReplaceAll(clean, "IDR", "")
	clean = strings.ReplaceAll(clean, ",", "")
	clean = strings.ReplaceAll(clean, ".", "")
	clean = strings.TrimSpace(clean)

	if m := salRangeRe.FindStringSubmatch(clean); len(m) > 2 {
		minV, err1 := strconv.Atoi(m[1])
		maxV, err2 := strconv.Atoi(m[2])
		if err1 == nil && err2 == nil {
			return &minV, &maxV
		}
	}

	nums := salNumRe.FindAllString(clean, -1)
	if len(nums) >= 2 {
		minV, err1 := strconv.Atoi(nums[0])
		maxV, err2 := strconv.Atoi(nums[1])
		if err1 == nil && err2 == nil {
			return &minV, &maxV
		}
	} else if len(nums) == 1 {
		minV, err := strconv.Atoi(nums[0])
		if err == nil {
			return &minV, nil
		}
	}
	return nil, nil
}

func GenerateJobID(source, rawIdentifier string) string {
	src := strings.ToLower(strings.TrimSpace(source))
	if src == "" {
		src = "unknown"
	}
	raw := strings.TrimSpace(rawIdentifier)
	combined := fmt.Sprintf("%s%s", src, raw)
	hasher := md5.New()
	hasher.Write([]byte(combined))
	hashStr := hex.EncodeToString(hasher.Sum(nil))
	if len(hashStr) > 12 {
		hashStr = hashStr[:12]
	}
	return fmt.Sprintf("%s_%s", src, hashStr)
}

func GenerateContentSignature(title, company, location string) string {
	t := strings.TrimSpace(nonAlphaNumRe.ReplaceAllString(strings.ToLower(title), " "))
	c := strings.TrimSpace(nonAlphaNumRe.ReplaceAllString(strings.ToLower(company), " "))
	l := strings.TrimSpace(nonAlphaNumRe.ReplaceAllString(strings.ToLower(location), " "))
	if t == "" || c == "" || c == "unknown" || c == "unknown company" {
		return ""
	}
	combined := fmt.Sprintf("%s|%s|%s", t, c, l)
	sum := md5.Sum([]byte(combined))
	hashStr := hex.EncodeToString(sum[:])
	if len(hashStr) > 12 {
		hashStr = hashStr[:12]
	}
	return fmt.Sprintf("sig_%s", hashStr)
}

func FormatJobSalary(salary *string, salaryMin, salaryMax *int) string {
	if salary != nil && strings.TrimSpace(*salary) != "" {
		return FormatSalary(*salary)
	}
	if salaryMin != nil || salaryMax != nil {
		sMin := ""
		if salaryMin != nil {
			sMin = fmt.Sprintf("%d", *salaryMin)
		}
		sMax := ""
		if salaryMax != nil {
			sMax = fmt.Sprintf("%d", *salaryMax)
		}
		raw := strings.Trim(fmt.Sprintf("%s - %s", sMin, sMax), " -")
		return FormatSalary(raw)
	}
	return "Not disclosed"
}

