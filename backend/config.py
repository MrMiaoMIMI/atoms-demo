"""Runtime configuration. Everything is env-driven; no key means Mock mode."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent
load_dotenv(BASE_DIR / ".env")

DATA_DIR = Path(os.getenv("DATA_DIR", str(BASE_DIR / "data"))).resolve()
APPS_DIR = DATA_DIR / "apps"
BUILD_DIR = DATA_DIR / ".build"
DB_PATH = DATA_DIR / "atoms.db"
for _p in (DATA_DIR, APPS_DIR, BUILD_DIR):
    _p.mkdir(parents=True, exist_ok=True)

LLM_API_KEY = os.getenv("LLM_API_KEY", "").strip()
LLM_BASE_URL = os.getenv("LLM_BASE_URL", "https://api.deepseek.com").rstrip("/")
LLM_MODEL = os.getenv("LLM_MODEL", "deepseek-flash")
LLM_TIMEOUT = float(os.getenv("LLM_TIMEOUT", "180"))
LLM_TEMPERATURE = float(os.getenv("LLM_TEMPERATURE", "0.4"))
# Retry policy for every generation call (planner / coder / consult / mike).
# LLM_MAX_RETRIES counts retries after the first attempt, so the default means
# up to 4 total attempts. Backoff doubles each round and is capped at 8s.
LLM_MAX_RETRIES = max(0, int(os.getenv("LLM_MAX_RETRIES", "3")))
LLM_RETRY_BACKOFF = max(0.0, float(os.getenv("LLM_RETRY_BACKOFF", "1.0")))
LLM_RETRY_BACKOFF_MAX = max(0.0, float(os.getenv("LLM_RETRY_BACKOFF_MAX", "8.0")))
# Per-request output budget. DeepSeek may reject values above its own ceiling;
# llm.py then falls back to 8192 automatically for the rest of the process.
LLM_MAX_TOKENS = max(1, int(os.getenv("LLM_MAX_TOKENS", "16384")))
# How many consecutive requests (initial + continuations) may be used when a
# single completion ends with finish_reason=length.
LLM_CONTINUATION_PASSES = max(1, int(os.getenv("LLM_CONTINUATION_PASSES", "3")))

# Large-file guard for generated sources.
# Above WARN: surface a warning in the timeline. Above SPLIT: ask the model to
# split frontend TS/TSX files before review/build. Set FILE_SPLIT=0 to disable.
FILE_SIZE_WARN_CHARS = max(0, int(os.getenv("FILE_SIZE_WARN_CHARS", "12000")))
FILE_SIZE_SPLIT_CHARS = max(0, int(os.getenv("FILE_SIZE_SPLIT_CHARS", "20000")))
FILE_SPLIT_MAX_FILES = max(2, int(os.getenv("FILE_SPLIT_MAX_FILES", "8")))
FILE_SPLIT = os.getenv("FILE_SPLIT", "1") != "0"
# Project naming is a background side call; never let it block the workspace.
TITLE_TIMEOUT = float(os.getenv("TITLE_TIMEOUT", "12"))
LLM_MODE = "deepseek" if LLM_API_KEY else "mock"
AUTO_REPAIR = os.getenv("AUTO_REPAIR", "1") != "0"

# Generated app runtime (each project backend is a dedicated uvicorn process).
MAX_RUNNING_APPS = max(1, int(os.getenv("MAX_RUNNING_APPS", "2")))
GENERATED_APP_MEMORY_MB = max(0, int(os.getenv("GENERATED_APP_MEMORY_MB", "256")))
RUNTIME_START_TIMEOUT = float(os.getenv("RUNTIME_START_TIMEOUT", "20"))
FRONTEND_BUILD_TIMEOUT = float(os.getenv("FRONTEND_BUILD_TIMEOUT", "120"))

# Shared Node toolchain used only to bundle generated React sources for preview.
PREVIEW_NODE_MODULES = Path(
    os.getenv("PREVIEW_NODE_MODULES", str(BASE_DIR / "runtime" / "frontend" / "node_modules"))
).resolve()
