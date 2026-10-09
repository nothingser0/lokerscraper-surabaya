import html
import logging
import re
import unicodedata
from datetime import datetime
from typing import Optional, Any, Tuple

logger = logging.getLogger(__name__)

_TAG_RE = re.compile(r"<[^>]+>")
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_WS_RE = re.compile(r"\s+")

_WEEKDAYS = [
    "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu",
]

_MONTHS = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

_DATE_RE = re.compile(
    r"(?P<y1>\d{4})[-/](?P<m1>\d{1,2})[-/](?P<d1>\d{1,2})|(?P<d2>\d{1,2})[-/](?P<m2>\d{1,2})[-/](?P<y2>\d{4})"
)

_NUM_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:jt|juta|m|rb|ribu|k)", re.IGNORECASE)


def parse_salary_label(label: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    if not label:
        return None, None
    clean = label.replace("Rp", "").replace("IDR", "").replace(",", "").replace(".", "").strip()
    m = re.search(r"(\d+)\s*(?:–|-|to|s/d)\s*(\d+)", clean, re.IGNORECASE)
    if m:
        try:
            return int(m.group(1)), int(m.group(2))
        except ValueError:
            pass
    nums = re.findall(r"\b\d+\b", clean)
    if len(nums) >= 2:
        try:
            return int(nums[0]), int(nums[1])
        except ValueError:
            pass
    elif len(nums) == 1:
        try:
            return int(nums[0]), None
        except ValueError:
            pass
    return None, None


_KALIBRR_EXP_MAP = {
    200: "1-3 tahun",
    400: "5+ tahun",
}

_KALIBRR_EDU_MAP = {
    200: "SMA/SMK",
    550: "D3/S1 (Diploma/Sarjana)",
}

_GLINTS_EDU_MAP = {
    "BACHELOR": "S1",
    "DIPLOMA": "D1-D4",
    "HIGH_SCHOOL": "SMA/SMK",
    "MASTER": "S2",
}

_EXPERIENCE_LEVEL_MAP = {
    "internship": "Magang",
    "entry level": "Level Pemula",
    "associate": "Level Asosiat",
    "mid-senior level": "Level Menengah-Senior",
    "director": "Direktur",
    "executive": "Eksekutif",
    "not applicable": None,
    "": None,
}


def decode_kalibrr_experience(code: Any) -> Optional[str]:
    if code is None:
        return None
    try:
        val = int(code)
        return _KALIBRR_EXP_MAP.get(val)
    except (ValueError, TypeError):
        return None


def decode_kalibrr_education(code: Any) -> Optional[str]:
    if code is None:
        return None
    try:
        val = int(code)
        return _KALIBRR_EDU_MAP.get(val)
    except (ValueError, TypeError):
        return None


def decode_glints_education(code: Any) -> Optional[str]:
    if not code:
        return None
    return _GLINTS_EDU_MAP.get(str(code).upper())


def format_experience(value: Optional[str]) -> str:
    if not value:
        return "N/A"
    text = sanitize_text(str(value)).strip()
    key = text.lower()
    mapped = _EXPERIENCE_LEVEL_MAP.get(key)
    if mapped is not None:
        return mapped
    return text


_BENEFIT_MAP = {
    "car": "Mobil Dinas",
    "child_care": "Fasilitas Penitipan Anak",
    "family_leave": "Cuti Keluarga",
    "flexitime": "Jam Kerja Fleksibel",
    "life_ins": "Asuransi Jiwa",
    "mat_pat_leave": "Cuti Melahirkan/Ayah",
    "med_ins": "Asuransi Kesehatan",
    "med_plans": "Paket Kesehatan",
    "paid_holidays": "Libur Berbayar",
    "perf_bonus": "Bonus Kinerja",
    "sick_leave": "Izin Sakit",
    "single_leave": "Cuti Lajang",
    "special_for_women": "Fasilitas Khusus Wanita",
    "trans": "Tunjangan Transportasi",
    "wfh": "Bisa Kerja dari Rumah",
    "competitivesalary": "Gaji Kompetitif",
    "bonussystem": "Sistem Bonus",
    "casualdresscode": "Busana Santai",
    "maternityleave": "Cuti Melahirkan",
    "paidsickdays": "Izin Sakit Berbayar",
    "professionaldevelopment": "Pengembangan Profesional",
    "wellnessprogram": "Program Kesehatan",
    "freemeals": "Makan Gratis",
    "teambuilding": "Kegiatan Team Building",
    "employeediscounts": "Diskon Karyawan",
    "annual bonus": "Bonus Tahunan",
    "facility reimbursement": "Reimbursement Fasilitas",
    "birthday treat": "Hadiah Ulang Tahun",
    "companyoutings": "Kegiatan Perusahaan (Company Outing)",
    "freelunch": "Makan Siang Gratis",
    "gymmembership": "Keanggotaan Gym",
    "internationalexposure": "Eksposur Internasional",
    "medicalleave": "Cuti Sakit (Medis)",
    "periodleave": "Cuti Haid",
    "selfdevelopmentallowance": "Tunjangan Pengembangan Diri",
    "transport": "Tunjangan Transportasi",
    "vacationtime": "Waktu Libur",
    "early wages program": "Program Gaji Awal",
    "flexible working environment": "Lingkungan Kerja Fleksibel",
    "health insurance": "Asuransi Kesehatan",
    "personal loan": "Pinjaman Karyawan",
    "sign on bonus": "Bonus Tanda Tangan",
}


def decode_benefit(raw: Any) -> Optional[str]:
    if raw is None:
        return None
    text = str(raw).strip()
    if not text:
        return None
    key = text.replace("-", "_").lower()
    if key in _BENEFIT_MAP:
        return _BENEFIT_MAP[key]
    return text


def sanitize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = _TAG_RE.sub(" ", text)
    text = unicodedata.normalize("NFKC", text)
    text = _CTRL_RE.sub("", text)
    return _WS_RE.sub(" ", text).strip()


def format_date(value: Optional[str]) -> str:
    if not value:
        return "N/A"
    value = str(value).strip()

    iso = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso)
        return f"{_WEEKDAYS[dt.weekday()]}, {dt.day} {_MONTHS[dt.month - 1]} {dt.year}"
    except ValueError:
        pass

    m = _DATE_RE.match(value)
    if m:
        if m.group("y1"):
            y, mo, d = int(m.group("y1")), int(m.group("m1")), int(m.group("d1"))
        else:
            d, mo, y = int(m.group("d2")), int(m.group("m2")), int(m.group("y2"))
        try:
            dt = datetime(y, mo, d)
            return f"{_WEEKDAYS[dt.weekday()]}, {dt.day} {_MONTHS[dt.month - 1]} {dt.year}"
        except ValueError:
            pass

    return value or "N/A"


_JOB_TYPE_MAP = {
    "full_time": "Penuh Waktu",
    "fulltime": "Penuh Waktu",
    "full time": "Penuh Waktu",
    "full-time": "Penuh Waktu",
    "permanent": "Tetap",
    "part_time": "Paruh Waktu",
    "parttime": "Paruh Waktu",
    "part time": "Paruh Waktu",
    "part-time": "Paruh Waktu",
    "contract": "Kontrak",
    "contract/temp": "Kontrak/Sementara",
    "contract temp": "Kontrak/Sementara",
    "temporary": "Sementara",
    "temp": "Sementara",
    "internship": "Magang",
    "intern": "Magang",
    "project_based": "Berbasis Proyek",
    "project based": "Berbasis Proyek",
    "project-based": "Berbasis Proyek",
    "freelance": "Freelance",
    "remote": "Remote",
    "hybrid": "Hybrid",
    "onsite": "On-site",
    "on_site": "On-site",
}

_WORK_MODE_MAP = {
    "remote": "Remote",
    "hybrid": "Hybrid",
    "onsite": "On-site",
    "on site": "On-site",
    "on-site": "On-site",
}


def format_job_type(value: Optional[str]) -> str:
    if not value:
        return "N/A"
    text = sanitize_text(str(value)).strip()
    if not text:
        return "N/A"
    key = text.replace("-", " ").replace("_", " ").lower()
    key = _WS_RE.sub(" ", key).strip()
    return _JOB_TYPE_MAP.get(key, text)


def format_work_mode(value: Optional[str]) -> str:
    if not value:
        return "N/A"
    text = sanitize_text(str(value)).strip().lower()
    return _WORK_MODE_MAP.get(text, sanitize_text(str(value)).strip() or "N/A")


_EN_GLOSSARY = [
    ("requirements", "Persyaratan"),
    ("responsibilities", "Tanggung Jawab"),
    ("qualifications", "Kualifikasi"),
    ("job description", "Deskripsi Pekerjaan"),
    ("job requirements", "Persyaratan Pekerjaan"),
    ("benefits", "Fasilitas"),
    ("work from home", "Bisa Kerja dari Rumah"),
    ("work from anywhere", "Bisa Kerja dari Mana Saja"),
    ("remote work", "Kerja Jarak Jauh"),
    ("hybrid working", "Kerja Hibrida"),
    ("flexible working hours", "Jam Kerja Fleksibel"),
    ("full-time", "Penuh Waktu"),
    ("part-time", "Paruh Waktu"),
    ("internship", "Magang"),
    ("contract", "Kontrak"),
    ("salary", "Gaji"),
    ("salary range", "Kisaran Gaji"),
    ("negotiable", "Bisa dinegosiasikan"),
    ("competitive salary", "Gaji Kompetitif"),
    ("health insurance", "Asuransi Kesehatan"),
    ("bpjs ketenagakerjaan", "BPJS Ketenagakerjaan"),
    ("bpjs kesehatan", "BPJS Kesehatan"),
    ("annual leave", "Cuti Tahunan"),
    ("paid time off", "Cuti Berbayar"),
    ("performance bonus", "Bonus Kinerja"),
    ("religious holiday allowance", "Tunjangan Hari Raya (THR)"),
    ("meal allowance", "Uang Makan"),
    ("transport allowance", "Uang Transport"),
    ("career growth", "Jenjang Karir"),
    ("career development", "Pengembangan Karir"),
    ("years of experience", "tahun pengalaman"),
    ("bachelor degree", "S1"),
    ("diploma degree", "D3"),
    ("high school", "SMA/SMK"),
    ("fresh graduate", "Lulusan Baru"),
    ("good communication", "Komunikasi yang Baik"),
    ("team player", "Mampu Bekerja Sama"),
    ("problem solving", "Pemecahan Masalah"),
    ("work under pressure", "Bekerja di Bawah Tekanan"),
    ("attention to detail", "Teliti"),
    ("critical thinking", "Berpikir Kritis"),
    ("leadership skills", "Jiwa Kepemimpinan"),
    ("fast learner", "Cepat Belajar"),
    ("self motivated", "Termotivasi"),
    ("fluent in english", "Fasih Berbahasa Inggris"),
    ("proficiency in", "Kemahiran dalam"),
    ("experience in", "Pengalaman dalam"),
    ("responsible for", "Bertanggung jawab untuk"),
    ("proven experience", "Pengalaman Terbukti"),
    ("minimum experience", "Pengalaman Minimum"),
    ("key responsibilities", "Tanggung Jawab Utama"),
    ("what you will do", "Tugas yang Dikerjakan"),
    ("what we offer", "Fasilitas yang Diberikan"),
    ("about the role", "Tentang Pekerjaan"),
    ("about the company", "Tentang Perusahaan"),
    ("how to apply", "Cara Melamar"),
    ("must have", "Wajib Dimiliki"),
    ("nice to have", "Nilai Tambah"),
    ("preferred skills", "Keahlian yang Disukai"),
    ("required skills", "Keahlian yang Dibutuhkan"),
    ("role and responsibilities", "Peran dan Tanggung Jawab"),
    ("terms and conditions", "Syarat dan Ketentuan"),
    ("equal opportunity", "Kesempatan Setara"),
    ("working hours", "Jam Kerja"),
    ("office hours", "Jam Kantor"),
    ("on-site", "Di Tempat (On-site)"),
    ("relocation assistance", "Bantuan Relokasi"),
    ("signing bonus", "Bonus Perekrutan"),
    ("stock options", "Opsi Saham"),
    ("gym membership", "Keanggotaan Gym"),
    ("maternity leave", "Cuti Melahirkan"),
    ("paternity leave", "Cuti Ayah"),
    ("life insurance", "Asuransi Jiwa"),
    ("vision insurance", "Asuransi Mata"),
    ("dental insurance", "Asuransi Gigi"),
    ("professional training", "Pelatihan Profesional"),
    ("education allowance", "Tunjangan Pendidikan"),
    ("overtime pay", "Uang Lembur"),
    ("laptop provided", "Disediakan Laptop"),
    ("free lunch", "Makan Siang Gratis"),
    ("free snacks", "Camilan Gratis"),
    ("free parking", "Parkir Gratis"),
    ("shuttle service", "Layanan Antar-Jemput"),
    ("probation period", "Masa Percobaan"),
    ("immediate start", "Bisa Langsung Masuk"),
    ("open for all", "Terbuka untuk Umum"),
    ("urgent hiring", "Dibutuhkan Segera"),
    ("apply now", "Lamar Sekarang"),
    ("send your cv", "Kirim CV Anda"),
    ("contact us", "Hubungi Kami"),
    ("click here", "Klik di sini"),
    ("please", "Silakan"),
    ("thank you", "Terima kasih"),
    ("etc", "dll"),
]

_EN_GLOSSARY.sort(key=lambda t: len(t[0]), reverse=True)


def translate_description(text: Optional[str]) -> str:
    if not text:
        return ""
    result = sanitize_text(text)
    if not result:
        return ""

    for en, id_ in _EN_GLOSSARY:
        if not id_:
            continue
        result = re.sub(
            r"\b" + re.escape(en) + r"\b",
            id_,
            result,
            flags=re.IGNORECASE,
        )

    return result


def format_salary(value: Optional[str]) -> str:
    if not value:
        return "Not disclosed"

    text = sanitize_text(str(value)).strip()
    if not text:
        return "Not disclosed"

    lower = text.lower()
    if lower in ("none", "null", "not disclosed", "competitive", "negotiable"):
        return "Not disclosed"

    text = text.replace("{", "").replace("}", "").replace("'", "").replace('"', "")

    def _compact(num_str: str) -> str:
        try:
            n = float(num_str)
        except (ValueError, TypeError):
            return num_str
        if n >= 1_000_000:
            millions = n / 1_000_000
            if millions == int(millions):
                return f"Rp{int(millions)}jt"
            return f"Rp{millions:.1f}jt"
        if n >= 1_000:
            thousands = n / 1_000
            if thousands == int(thousands):
                return f"Rp{int(thousands)}rb"
            return f"Rp{thousands:.1f}rb"
        return f"Rp{int(n)}"

    def _parse_amount(tok: str) -> str:
        tok = tok.strip()
        tok = re.sub(r"^(?:idr|rp|usd|sgd|eur)\s*", "", tok, flags=re.IGNORECASE)
        tok = re.sub(r"\s*(?:per|/)?\s*(month|bulan|year|tahun|day|hari)\b.*$", "", tok, flags=re.IGNORECASE).strip()
        if not tok:
            return ""
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(m|jt|juta|million|mil)", tok, flags=re.IGNORECASE)
        if m:
            return _compact(str(float(m.group(1)) * 1_000_000))
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(k|rb|ribu|thousand)", tok, flags=re.IGNORECASE)
        if m:
            return _compact(str(float(m.group(1)) * 1_000))
        m = re.search(r"(\d+(?:[.,]\d+)*(?:\.\d+)?)\s*(m|jt|juta|million|mil|k|rb|ribu)", tok, flags=re.IGNORECASE)
        if m:
            num = m.group(1).replace(",", "").replace(".", "")
            unit = m.group(2).lower()
            mult = 1_000_000 if unit in ("m", "jt", "juta", "million", "mil") else 1_000
            return _compact(str(float(num) * mult))
        bare = tok.replace(",", "").replace(".", "")
        if re.fullmatch(r"\d+", bare):
            return _compact(bare)
        return tok

    text = re.sub(r"\b(start|end|min|max|minimum|maximum|salary)\s*[:=]", "|", text, flags=re.IGNORECASE)
    tokens = re.split(r"\s*[-–—~|]\s*", text)

    out_parts = []
    for token in tokens:
        token = token.strip()
        if not token:
            continue
        if token.lower() in ("up to", "from"):
            continue
        parsed = _parse_amount(token)
        if parsed:
            out_parts.append(parsed)

    seen = set()
    unique = []
    for p in out_parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    if not unique:
        return "Not disclosed"

    return " - ".join(unique)


def translate_to_indonesian(text: Optional[str]) -> str:
    cleaned = text if text else ""
    cleaned = _normalize_description(cleaned)
    if not cleaned:
        return ""

    try:
        from config import config
    except Exception:
        return cleaned

    api_key = getattr(config, "DEEPL_API_KEY", "")
    if not api_key:
        return cleaned

    api_url = getattr(config, "DEEPL_API_URL", "https://api-free.deepl.com/v2/translate")
    try:
        import requests

        resp = requests.post(
            api_url,
            headers={
                "Authorization": f"DeepL-Auth-Key {api_key}",
                "Content-Type": "application/json",
            },
            json={
                "text": [cleaned],
                "target_lang": "ID",
            },
            timeout=15,
        )
        if resp.status_code == 200:
            data = resp.json()
            translations = data.get("translations", [])
            if translations and translations[0].get("text"):
                return _normalize_description(translations[0]["text"])
        logger.warning(
            f"DeepL translation failed with status {resp.status_code}; returning original text."
        )
    except Exception as e:
        logger.warning(f"DeepL translation error ({e}); returning original text.")

    return cleaned


def _normalize_description(text: Optional[str]) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = re.sub(r"(?i)<br\s*/?>|</p>|</h\d>|</div>|</ul>|</ol>|<button[^>]*>|</button>", "\n", text)
    text = re.sub(r"(?i)<li[^>]*>", "\n• ", text)
    text = re.sub(r"(?i)<ul[^>]*>|<ol[^>]*>", "\n", text)
    text = _TAG_RE.sub(" ", text)
    text = unicodedata.normalize("NFKC", text)
    text = re.sub(r"[\x00-\x08\x0b\x0c\x0e-\x1f\x7f-\x9f]", "", text)
    lines = [re.sub(r"[ \t]+", " ", ln).strip() for ln in text.splitlines()]
    out: list = []
    for ln in lines:
        if ln:
            out.append(ln)
        elif out and out[-1] != "":
            out.append("")
    out = [ln for ln in out if ln and ln.strip().lower() not in ("show more", "show less")]
    return "\n".join(out).strip()


def clean_description(text: Optional[str]) -> str:
    return _normalize_description(text)


def draftjs_to_text(raw: Any) -> Optional[str]:
    if not isinstance(raw, dict):
        return None
    blocks = raw.get("blocks")
    if not isinstance(blocks, list) or not blocks:
        return None

    lines: list = []
    for block in blocks:
        if not isinstance(block, dict):
            continue
        text = block.get("text")
        if not isinstance(text, str):
            text = ""
        text = text.strip()
        btype = str(block.get("type") or "unstyled").lower()

        if btype in ("unordered-list-item", "ordered-list-item"):
            if text:
                lines.append(f"• {text}")
        elif btype.startswith("header"):
            if text:
                lines.append(text)
                lines.append("")
        else:
            if text:
                lines.append(text)
                lines.append("")

    while lines and lines[-1] == "":
        lines.pop()

    result = "\n".join(lines).strip()
    return result or None


def format_description(description: Optional[str], max_len: int = 500) -> str:
    translated = translate_to_indonesian(description)
    if not translated:
        return ""
    if len(translated) <= max_len:
        return translated
    cut = translated[:max_len]
    if "\n" in cut:
        cut = cut.rsplit("\n", 1)[0]
    return cut.rstrip() + "…"
