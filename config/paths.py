"""
config/paths.py  —  reads all project paths from .env, in one place.

Every path lives in .env (the single source you edit when something moves).
This module loads them so the rest of the code imports from one spot instead
of scattering os.getenv calls. load_dotenv() runs here so paths resolve no
matter which module imports this first.

.env keys:
  RAW_DIR        raw databook Excel folder
  PROCESSED_DIR  processed CSV output folder
  MACRO_DIR      (optional) central-bank/static data folder
"""

import os
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

RAW_DIR = Path(os.getenv("RAW_DIR"))
PROCESSED_DIR = Path(os.getenv("PROCESSED_DIR"))

_macro = os.getenv("MACRO_DIR")
MACRO_DIR = Path(_macro) if _macro else None