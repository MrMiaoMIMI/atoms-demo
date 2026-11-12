"""Runtime configuration. Everything is env-driven; no key means Mock mode."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
APPS_DIR = DATA_DIR / "apps"
DB_PATH = DATA_DIR / "atoms.db"
for _p in (DATA_DIR, APPS_DIR):
    _p.mkdir(parents=True, exist_ok=True)

LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-flash")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "180"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.4"))
LLM_MODE = "deepseek" if LLM_API_KEY else "mock"
AUTO_REPAIR = os.getenv("AUTO_REPAIR", "1") != "0"
