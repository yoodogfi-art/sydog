"""
config/paths.py  —  every filesystem path the project uses, resolved once.

Paths live in .env; this module is the ONLY place that reads them. Nothing else
in the project calls os.getenv for a path, so the writer (ingestion) and the
reader (storage) can never drift apart — they import the same object.

.env keys
---------
  RAW_DIR        raw databook Excel folder
  PROCESSED_DIR  processed CSV output folder
  MACRO_DIR      central-bank / static CSV folder
  EXTRA_BOOKS    ';'-separated Excel books outside RAW_DIR (network drives etc.)

A missing key falls back to the documented default below. Use /config to see
what actually resolved.
"""

from pathlib import Path

from config.env import get

DEFAULTS = {
    "RAW_DIR": r"C:\Users\User\databook_raw",
    "PROCESSED_DIR": r"C:\Users\User\databook_processed",
    "MACRO_DIR": r"C:\Users\User\databook_macro",
}

# Keys that fell back to a default. MACRO_DIR is optional, so it is tracked but
# never warned about: the macro folder simply may not exist yet.
def _path(key: str) -> Path:
    """Value from .env, else the documented default."""
    return Path(get(key) or DEFAULTS[key])


RAW_DIR = _path("RAW_DIR")
PROCESSED_DIR = _path("PROCESSED_DIR")
MACRO_DIR = _path("MACRO_DIR")

# Books that must be refreshed but do not live in RAW_DIR (e.g. the shared Z:
# drive book). Semicolon-separated so Windows drive letters survive.
EXTRA_BOOKS: list[Path] = [
    Path(p.strip()) for p in (get("EXTRA_BOOKS") or "").split(";") if p.strip()
]

