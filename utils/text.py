import html
import re
import unicodedata
from datetime import datetime
from typing import Optional

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
    "full_time": "Full-time",
    "fulltime": "Full-time",
    "full time": "Full-time",
    "part_time": "Part-time",
    "parttime": "Part-time",
    "part time": "Part-time",
    "contract": "Contract",
    "internship": "Internship",
    "intern": "Internship",
    "project_based": "Project-based",
    "project based": "Project-based",
    "freelance": "Freelance",
    "temporary": "Temporary",
    "permanent": "Permanent",
    "remote": "Remote",
    "hybrid": "Hybrid",
    "onsite": "On-site",
    "on_site": "On-site",
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
