import html
import re
import unicodedata
from typing import Optional

_TAG_RE = re.compile(r"<[^>]+>")
_CTRL_RE = re.compile(r"[\x00-\x1f\x7f-\x9f]")
_WS_RE = re.compile(r"\s+")

def sanitize_text(text: Optional[str]) -> str:
    if not text:
        return ""
    text = html.unescape(text)
    text = _TAG_RE.sub(" ", text)
    text = unicodedata.normalize("NFKC", text)
    text = _CTRL_RE.sub("", text)
    return _WS_RE.sub(" ", text).strip()
