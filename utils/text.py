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

_WEEKDAYS_ID = [
    "Senin", "Selasa", "Rabu", "Kamis", "Jumat", "Sabtu", "Minggu",
]

_MONTHS_ID = [
    "Januari", "Februari", "Maret", "April", "Mei", "Juni",
    "Juli", "Agustus", "September", "Oktober", "November", "Desember",
]

# Common ISO-ish date patterns: YYYY-MM-DD, YYYY/MM/DD, DD-MM-YYYY, DD/MM/YYYY
_DATE_RE = re.compile(
    r"(?P<y1>\d{4})[-/](?P<m1>\d{1,2})[-/](?P<d1>\d{1,2})|(?P<d2>\d{1,2})[-/](?P<m2>\d{1,2})[-/](?P<y2>\d{4})"
)

_NUM_RE = re.compile(r"(\d+(?:[.,]\d+)?)\s*(?:jt|juta|m|rb|ribu|k)", re.IGNORECASE)


def parse_salary_label(label: Optional[str]) -> tuple[Optional[int], Optional[int]]:
    """Parse salary label like 'Rp 10,000,000 – Rp 15,000,000 per month' into numeric min/max."""
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

# LinkedIn seniority-level labels → Indonesian.
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


def format_experience_id(value: Optional[str]) -> str:
    """Normalize an experience/seniority label to Indonesian (or pass through)."""
    if not value:
        return "N/A"
    text = sanitize_text(str(value)).strip()
    key = text.lower()
    mapped = _EXPERIENCE_LEVEL_MAP.get(key)
    if mapped is not None:
        return mapped
    return text


# Human-readable Indonesian labels for raw benefit slugs across sources.
# Keys are the exact raw slugs emitted by each platform. Unknown slugs are
# passed through unchanged (see decode_benefit) so no information is lost.
_BENEFIT_MAP = {
    # Kalibrr perks.types slugs
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
    # SejutaCita benefits slugs (camelCase)
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
    # SejutaCita benefits slugs (camelCase) discovered via live probe
    "companyoutings": "Kegiatan Perusahaan (Company Outing)",
    "freelunch": "Makan Siang Gratis",
    "gymmembership": "Keanggotaan Gym",
    "internationalexposure": "Eksposur Internasional",
    "medicalleave": "Cuti Sakit (Medis)",
    "periodleave": "Cuti Haid",
    "selfdevelopmentallowance": "Tunjangan Pengembangan Diri",
    "transport": "Tunjangan Transportasi",
    "vacationtime": "Waktu Libur",
    # SejutaCita free-text benefit labels (English → Indonesian)
    "early wages program": "Program Gaji Awal",
    "flexible working environment": "Lingkungan Kerja Fleksibel",
    "health insurance": "Asuransi Kesehatan",
    "personal loan": "Pinjaman Karyawan",
    "sign on bonus": "Bonus Tanda Tangan",
}


def decode_benefit(raw: Any) -> Optional[str]:
    """Map a raw benefit slug to a human-readable Indonesian label.

    Unknown slugs are returned as-is (normalized) so no benefit is dropped.
    ``None``/empty returns ``None``.
    """
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


def format_date_id(value: Optional[str]) -> str:
    """Format an ISO/date string as an Indonesian date: ``Senin, 20 Agustus 2025``.

    Accepts full ISO timestamps (``2025-08-20T...``), plain ``YYYY-MM-DD``,
    and ``DD-MM-YYYY``. Returns the original value when it cannot be parsed.
    """
    if not value:
        return "N/A"
    value = str(value).strip()

    # Full ISO timestamp: 2025-08-20T12:34:56+00:00
    iso = value.replace("Z", "+00:00")
    try:
        dt = datetime.fromisoformat(iso)
        return f"{_WEEKDAYS_ID[dt.weekday()]}, {dt.day} {_MONTHS_ID[dt.month - 1]} {dt.year}"
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
            return f"{_WEEKDAYS_ID[dt.weekday()]}, {dt.day} {_MONTHS_ID[dt.month - 1]} {dt.year}"
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

_WORK_MODE_MAP_ID = {
    "remote": "Remote",
    "hybrid": "Hybrid",
    "onsite": "On-site",
    "on site": "On-site",
    "on-site": "On-site",
}


def format_job_type_id(value: Optional[str]) -> str:
    """Normalize a job type string to a clean, human-readable label.

    Examples:
        ``FULL_TIME`` / ``Full time`` -> ``Full-time``
        ``PART_TIME``                -> ``Part-time``
        ``CONTRACT``                 -> ``Contract``
        ``PROJECT_BASED``            -> ``Project-based``
    """
    if not value:
        return "N/A"
    text = sanitize_text(str(value)).strip()
    if not text:
        return "N/A"
    key = text.replace("-", " ").replace("_", " ").lower()
    key = _WS_RE.sub(" ", key).strip()
    return _JOB_TYPE_MAP.get(key, text)


def format_work_mode_id(value: Optional[str]) -> str:
    """Normalize a work-mode string to a clean label (Remote/Hybrid/On-site)."""
    if not value:
        return "N/A"
    text = sanitize_text(str(value)).strip().lower()
    return _WORK_MODE_MAP_ID.get(text, sanitize_text(str(value)).strip() or "N/A")


# Offline English→Indonesian glossary for common job-description phrases and
# benefit labels. Used by translate_description_id() to humanize raw English
# text without any external API. Keys are matched case-insensitively as whole
# phrases (longest-first) to avoid partial-word collisions.
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
    ("life insurance", "Asuransi Jiwa"),
    ("paid leave", "Cuti Berbayar"),
    ("annual leave", "Cuti Tahunan"),
    ("sick leave", "Cuti Sakit"),
    ("maternity leave", "Cuti Melahirkan"),
    ("parental leave", "Cuti Orang Tua"),
    ("bonus", "Bonus"),
    ("performance bonus", "Bonus Kinerja"),
    ("career development", "Pengembangan Karier"),
    ("training", "Pelatihan"),
    ("opportunities for growth", "Peluang Berkembang"),
    ("experience", "Pengalaman"),
    ("years of experience", "Tahun Pengalaman"),
    ("entry level", "Level Pemula"),
    ("mid-senior level", "Level Menengah-Senior"),
    ("associate", "Asosiat"),
    ("director", "Direktur"),
    ("manager", "Manajer"),
    ("team", "Tim"),
    ("company", "Perusahaan"),
    ("clients", "Klien"),
    ("stakeholders", "Pemangku Kepentingan"),
    ("we are looking for", "Kami mencari"),
    ("we're looking for", "Kami mencari"),
    ("you will be responsible", "Anda akan bertanggung jawab"),
    ("you will", "Anda akan"),
    ("you'll", "Anda akan"),
    ("responsible for", "Bertanggung jawab atas"),
    ("good communication skills", "Kemampuan komunikasi yang baik"),
    ("communication skills", "Kemampuan komunikasi"),
    ("problem solving", "Pemecahan Masalah"),
    ("problem-solving", "Pemecahan Masalah"),
    ("attention to detail", "Ketelitian"),
    ("team player", "Bisa bekerja dalam tim"),
    ("fast learner", "Cepat belajar"),
    ("self-motivated", "Motivasi diri tinggi"),
    ("proficient in", "Mahir dalam"),
    ("familiar with", "Familiar dengan"),
    ("knowledge of", "Pengetahuan tentang"),
    ("experience with", "Pengalaman dengan"),
    ("experience in", "Pengalaman di bidang"),
    ("at least", "Minimal"),
    ("minimum", "Minimal"),
    ("preferred", "Diutamakan"),
    ("nice to have", "Nilai tambah"),
    ("plus", "Nilai tambah"),
    ("required", "Diwajibkan"),
    ("must have", "Wajib dimiliki"),
    ("is a plus", "Adalah nilai tambah"),
    ("bachelor", "Sarjana"),
    ("bachelor's degree", "Gelar Sarjana"),
    ("master's degree", "Gelar Magister"),
    ("degree in", "Gelar di bidang"),
    ("computer science", "Ilmu Komputer"),
    ("information technology", "Teknologi Informasi"),
    ("software engineer", "Software Engineer"),
    ("software developer", "Pengembang Perangkat Lunak"),
    ("web developer", "Pengembang Web"),
    ("mobile developer", "Pengembang Mobile"),
    ("frontend", "Frontend"),
    ("backend", "Backend"),
    ("fullstack", "Fullstack"),
    ("database", "Basis Data"),
    ("cloud", "Cloud"),
    ("api", "API"),
    ("agile", "Agile"),
    ("scrum", "Scrum"),
    ("english", "Bahasa Inggris"),
    ("indonesian", "Bahasa Indonesia"),
    ("fluent in", "Fasih dalam"),
    ("immediate", "Segera"),
    ("available", "Tersedia"),
    ("to apply", "Untuk melamar"),
    ("apply now", "Lamar sekarang"),
    ("click here", "Klik di sini"),
    ("please", "Silakan"),
    ("thank you", "Terima kasih"),
    ("etc", "dll"),
]

# Sort by phrase length (descending) so longer phrases match first.
_EN_GLOSSARY.sort(key=lambda t: len(t[0]), reverse=True)


def translate_description_id(text: Optional[str]) -> str:
    """Translate common English job-description phrases into Indonesian.

    This is a lightweight, offline glossary pass (no external API). Longer
    phrases are replaced first so sub-phrases do not clobber them. Only common
    terms are translated; technical/domain words are left untouched.
    """
    if not text:
        return ""
    result = sanitize_text(text)
    if not result:
        return ""

    # Whole-phrase, case-insensitive replacement.
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


def format_salary_id(value: Optional[str]) -> str:
    """Normalize a salary string into a readable Indonesian format.

    Examples:
        ``8000000`` / ``"8000000 - 12000000"`` -> ``Rp8jt - Rp12jt``
        ``"Rp 10.000.000 – Rp 15.000.000 per month"`` -> ``Rp10jt - Rp15jt``
        ``"{'start': 8000000, 'end': 12000000}"`` -> ``Rp8jt - Rp12jt``
        ``"IDR up to 25M"`` -> ``Rp25jt``
        ``"IDR 8M - 12M"`` -> ``Rp8jt - Rp12jt``
    """
    if not value:
        return "Not disclosed"

    text = sanitize_text(str(value)).strip()
    if not text:
        return "Not disclosed"

    lower = text.lower()
    if lower in ("none", "null", "not disclosed", "competitive", "negotiable"):
        return "Not disclosed"

    # Strip surrounding dict/brace notation and JSON quoting.
    text = text.replace("{", "").replace("}", "").replace("'", "").replace('"', "")

    def _compact(num_str: str) -> str:
        """Turn a plain number like 8000000 into ``Rp8jt``."""
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

    # Parse a single amount token into either a compacted "RpXjt" or a label.
    def _parse_amount(tok: str) -> str:
        tok = tok.strip()
        # Remove leading currency words.
        tok = re.sub(r"^(?:idr|rp|usd|sgd|eur)\s*", "", tok, flags=re.IGNORECASE)
        # Remove trailing qualifiers like "per month", "/month", "bulan".
        tok = re.sub(r"\s*(?:per|/)?\s*(month|bulan|year|tahun|day|hari)\b.*$", "", tok, flags=re.IGNORECASE).strip()
        if not tok:
            return ""
        # "8M" / "8 m" / "8jt" / "8 juta" -> compacted Rp.
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(m|jt|juta|million|mil)", tok, flags=re.IGNORECASE)
        if m:
            return _compact(str(float(m.group(1)) * 1_000_000))
        m = re.fullmatch(r"(\d+(?:\.\d+)?)\s*(k|rb|ribu|thousand)", tok, flags=re.IGNORECASE)
        if m:
            return _compact(str(float(m.group(1)) * 1_000))
        # "up to 25M" / "25M+" -> compact.
        m = re.search(r"(\d+(?:[.,]\d+)*(?:\.\d+)?)\s*(m|jt|juta|million|mil|k|rb|ribu)", tok, flags=re.IGNORECASE)
        if m:
            num = m.group(1).replace(",", "").replace(".", "")
            unit = m.group(2).lower()
            mult = 1_000_000 if unit in ("m", "jt", "juta", "million", "mil") else 1_000
            return _compact(str(float(num) * mult))
        # Strip thousands separators and detect a bare number.
        bare = tok.replace(",", "").replace(".", "")
        if re.fullmatch(r"\d+", bare):
            return _compact(bare)
        return tok

    # Split into range tokens. Handle both explicit ranges ("a - b") and dict
    # notation ("start: 8000000, end: 12000000") by splitting on separators AND
    # key fragments.
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

    # Dedup while preserving order.
    seen = set()
    unique = []
    for p in out_parts:
        if p not in seen:
            seen.add(p)
            unique.append(p)

    if not unique:
        return "Not disclosed"

    return " - ".join(unique)


def translate_to_id(text: Optional[str]) -> str:
    """Translate a job description to Bahasa Indonesia using DeepL.

    Translation is opt-in: when no DeepL key is configured, the original text
    is returned unchanged (no partial glossary translation). On API failure the
    original text is also returned so notifications never break.
    """
    cleaned = sanitize_text(text) if text else ""
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
                return sanitize_text(translations[0]["text"])
        logger.warning(
            f"DeepL translation failed with status {resp.status_code}; returning original text."
        )
    except Exception as e:
        logger.warning(f"DeepL translation error ({e}); returning original text.")

    return cleaned
