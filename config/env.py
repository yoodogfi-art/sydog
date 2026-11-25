"""
config/env.py  —  load .env. That's it.

.env is the source of truth, so two python-dotenv defaults are overridden:

  override=True   otherwise a leftover OS environment variable beats the file
                  and editing .env appears to do nothing.
  explicit path   otherwise the file is looked up from the current working
                  directory, so it loads from the project root but not from
                  Task Scheduler or an IDE run configuration.

Encoding is sniffed the same way storage/loader.py sniffs CSVs: Notepad's
"Unicode" is UTF-16, which a plain utf-8 read turns into nothing at all.

Anything not in .env falls back to the default in config/paths.py. No warnings
— /config reports the state when you ask for it.
"""

import io
import os
from pathlib import Path

from dotenv import dotenv_values

ROOT = Path(__file__).resolve().parents[1]
ENV_PATH = ROOT / ".env"

_ENCODINGS = ("utf-8-sig", "utf-8", "utf-16", "cp949")


def _read(path: Path) -> str | None:
    try:
        raw = path.read_bytes()
    except OSError:
        return None
    for enc in _ENCODINGS:
        try:
            text = raw.decode(enc)
        except (UnicodeDecodeError, UnicodeError):
            continue
        if "=" in text:        # decoded to something that looks like KEY=VALUE
            return text
    return None


def _load() -> dict[str, str]:
    text = _read(ENV_PATH)
    if text is None:
        return {}
    values = {k: v for k, v in dotenv_values(stream=io.StringIO(text)).items()
              if v is not None}
    os.environ.update(values)   # .env wins
    return values


LOADED = _load()


def get(key: str, default: str | None = None) -> str | None:
    return os.environ.get(key, default)
