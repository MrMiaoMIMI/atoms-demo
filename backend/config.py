"""Runtime configuration. Everything is env-driven; no key means Mock mode."""
import os
from pathlib import Path

from dotenv import load_dotenv

BASE_DIR = Path(__file__).resolve().parent

# Configuration is layered so local and production share secrets while keeping
# environment-specific values apart:
#   process/container env  >  backend/.env.{APP_ENV}  >  backend/.env
# APP_ENV comes from the process environment (Docker Compose sets it to
# "production"); running uvicorn directly defaults to "local".
APP_ENV = os.getenv("APP_ENV", "local").strip().lower()
_PROFILE_FILE = BASE_DIR / f".env.{APP_ENV}"

# Load the profile first with override=False so it only fills keys that are not
# already set by the real process environment. Loading the shared file second
# means it can only fill keys the profile did not define, which gives the
# precedence above.
if _PROFILE_FILE.is_file():
    load_dotenv(_PROFILE_FILE, override=False)
load_dotenv(BASE_DIR / ".env", override=False)

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

# First-build visual polish. The pass only edits presentation files and is
# best-effort: if it cannot rebuild, the functional build is kept unchanged.
DESIGN_PASS_FIRST_BUILD = os.getenv("DESIGN_PASS_FIRST_BUILD", "1") != "0"
DESIGN_PASS_MAX_STEPS = max(4, int(os.getenv("DESIGN_PASS_MAX_STEPS", "16")))
DESIGN_PASS_SECONDS = max(60.0, float(os.getenv("DESIGN_PASS_SECONDS", "420")))
DESIGN_PASS_MAX_TOOL_CALLS = max(
    8, int(os.getenv("DESIGN_PASS_MAX_TOOL_CALLS", "120"))
)

# ---------------------------------------------------------------------------
# Agent tool loop
# ---------------------------------------------------------------------------
# The unified build/iteration path uses native function calling. The legacy
# per-file generator remains available for providers without tool support.
AGENT_TOOL_LOOP = os.getenv("AGENT_TOOL_LOOP", "1") != "0"
AGENT_MAX_STEPS_FIRST_BUILD = max(20, int(os.getenv("AGENT_MAX_STEPS_FIRST_BUILD", "96")))
AGENT_MAX_STEPS_ITERATION = max(12, int(os.getenv("AGENT_MAX_STEPS_ITERATION", "64")))
AGENT_MAX_SECONDS_FIRST_BUILD = float(os.getenv("AGENT_MAX_SECONDS_FIRST_BUILD", "1200"))
AGENT_MAX_SECONDS_ITERATION = float(os.getenv("AGENT_MAX_SECONDS_ITERATION", "600"))
AGENT_MAX_TOOL_CALLS = max(20, int(os.getenv("AGENT_MAX_TOOL_CALLS", "320")))
AGENT_MAX_TOOL_CALLS_PER_STEP = max(1, int(os.getenv("AGENT_MAX_TOOL_CALLS_PER_STEP", "8")))
AGENT_MAX_NO_PROGRESS_STEPS = max(2, int(os.getenv("AGENT_MAX_NO_PROGRESS_STEPS", "5")))
AGENT_REPAIR_MAX_ROUNDS = max(0, int(os.getenv("AGENT_REPAIR_MAX_ROUNDS", "2")))
# Inline the whole source tree when it is small; otherwise use tools for reads.
AGENT_CONTEXT_INLINE_CHARS = max(0, int(os.getenv("AGENT_CONTEXT_INLINE_CHARS", "40000")))
AGENT_CONTEXT_FILE_CHARS = max(0, int(os.getenv("AGENT_CONTEXT_FILE_CHARS", "12000")))

# Execution step views (read_file snapshot / grep / build logs / ...). Each
# generation prunes old views so the demo database cannot grow without bound.
# The step rows stay; only the payload is dropped and the step stops being
# clickable after a refresh.
EXECUTION_VIEW_KEEP_RUNS = max(1, int(os.getenv("EXECUTION_VIEW_KEEP_RUNS", "20")))
EXECUTION_VIEW_MAX_BYTES = max(
    0, int(os.getenv("EXECUTION_VIEW_MAX_BYTES", "20000000"))
)

# Generated app runtime (each project backend is a dedicated uvicorn process).
MAX_RUNNING_APPS = max(1, int(os.getenv("MAX_RUNNING_APPS", "2")))
GENERATED_APP_MEMORY_MB = max(0, int(os.getenv("GENERATED_APP_MEMORY_MB", "256")))
RUNTIME_START_TIMEOUT = float(os.getenv("RUNTIME_START_TIMEOUT", "20"))
FRONTEND_BUILD_TIMEOUT = float(os.getenv("FRONTEND_BUILD_TIMEOUT", "120"))
# esbuild only strips types. A real tsc pass catches wrong component props and
# third-party API misuse before the iframe shows a blank screen.
FRONTEND_TYPECHECK = os.getenv("FRONTEND_TYPECHECK", "1") != "0"
FRONTEND_TYPECHECK_TIMEOUT = float(os.getenv("FRONTEND_TYPECHECK_TIMEOUT", "60"))

# Shared Node toolchain used only to bundle generated React sources for preview.
PREVIEW_NODE_MODULES = Path(
    os.getenv("PREVIEW_NODE_MODULES", str(BASE_DIR / "runtime" / "frontend" / "node_modules"))
).resolve()

# ---------------------------------------------------------------------------
# Accounts, sessions and email
# ---------------------------------------------------------------------------
# Public origin used to build verification / reset links and the OAuth
# redirect. Prefer an explicit value in .env.production; when empty (the local
# default) the origin of the incoming request is used instead.
PUBLIC_BASE_URL = os.getenv("PUBLIC_BASE_URL", "").rstrip("/")

AUTH_COOKIE_NAME = os.getenv("AUTH_COOKIE_NAME", "atoms_session")
# Browsers only send Secure cookies over HTTPS. Keep it off for local HTTP.
AUTH_COOKIE_SECURE = os.getenv("AUTH_COOKIE_SECURE", "0") == "1"
AUTH_SESSION_DAYS = max(1, int(os.getenv("AUTH_SESSION_DAYS", "30")))
AUTH_VERIFY_TTL_HOURS = max(1, int(os.getenv("AUTH_VERIFY_TTL_HOURS", "24")))
AUTH_RESET_TTL_MINUTES = max(5, int(os.getenv("AUTH_RESET_TTL_MINUTES", "60")))

# The one-click demo login creates accounts with this password. It is shown
# to the user in a tip after the account is created.
AUTH_DEMO_PASSWORD = os.getenv("AUTH_DEMO_PASSWORD", "AtomsDemo2026")
AUTH_DEMO_QUICK_LOGIN = os.getenv("AUTH_DEMO_QUICK_LOGIN", "1") != "0"

# Verification / reset links are only returned to the browser when mail is
# not configured (or when explicitly enabled). This keeps the demo flow
# usable without an SMTP account.
_auth_dev_links_env = os.getenv("AUTH_DEV_LINKS")
AUTH_DEV_LINKS = (
    _auth_dev_links_env == "1"
    if _auth_dev_links_env is not None
    else None  # auto: enabled when SMTP is not configured
)

# Password hashing (stdlib scrypt).
SCRYPT_N = int(os.getenv("SCRYPT_N", "16384"))
SCRYPT_R = int(os.getenv("SCRYPT_R", "8"))
SCRYPT_P = int(os.getenv("SCRYPT_P", "1"))

# Google OAuth (server-side authorization-code flow).
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "").strip()
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "").strip()
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", "").strip()

# SMTP (QQ Mail: smtp.qq.com, 465/ssl, authorization code as password).
SMTP_HOST = os.getenv("SMTP_HOST", "").strip()
SMTP_PORT = int(os.getenv("SMTP_PORT", "465"))
SMTP_TLS = os.getenv("SMTP_TLS", "ssl").strip().lower()  # ssl | starttls | none
SMTP_USER = os.getenv("SMTP_USER", "").strip()
SMTP_PASS = os.getenv("SMTP_PASS", "")
SMTP_FROM = os.getenv("SMTP_FROM", "").strip() or SMTP_USER
SMTP_FROM_NAME = os.getenv("SMTP_FROM_NAME", "Atoms Demo").strip()
SMTP_TIMEOUT = float(os.getenv("SMTP_TIMEOUT", "15"))
