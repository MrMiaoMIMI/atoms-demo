"""Authentication primitives: passwords, sessions, tokens and rate limits.

Only the Python standard library is used for crypto so the demo keeps its
small dependency set. Sessions are opaque random tokens; the database stores
their SHA-256 digest, never the cookie value itself.
"""
from __future__ import annotations

import asyncio
import hashlib
import hmac
import re
import secrets
import time
from collections import defaultdict, deque
from datetime import datetime, timedelta, timezone
from urllib.parse import quote, urlencode

from fastapi import HTTPException, Request, Response

import config
import db
import mailer

EMAIL_RE = re.compile(r"^[^\s@]+@[^\s@]+\.[^\s@]{2,}$")
PASSWORD_MIN = 8
PASSWORD_MAX = 64


# ---------------------------------------------------------------------------
# Validation
# ---------------------------------------------------------------------------

def normalize_email(value: str | None) -> str:
    return (value or "").strip().lower()


def is_valid_email(value: str | None) -> bool:
    email = normalize_email(value)
    if not email or len(email) > 254 or len(email) < 5:
        return False
    if not EMAIL_RE.match(email):
        return False
    local, _, domain = email.partition("@")
    if not local or not domain:
        return False
    if ".." in email or domain.startswith(".") or domain.endswith("."):
        return False
    return "." in domain


def validate_password(password: str) -> str | None:
    if len(password) < PASSWORD_MIN:
        return f"密码至少需要 {PASSWORD_MIN} 个字符"
    if len(password) > PASSWORD_MAX:
        return f"密码长度不能超过 {PASSWORD_MAX} 个字符"
    if not re.search(r"[A-Za-z]", password):
        return "密码需要包含字母"
    if not re.search(r"\d", password):
        return "密码需要包含数字"
    return None


# ---------------------------------------------------------------------------
# Password hashing (scrypt)
# ---------------------------------------------------------------------------

def hash_password(password: str) -> str:
    salt = secrets.token_bytes(16)
    digest = hashlib.scrypt(
        password.encode("utf-8"),
        salt=salt,
        n=config.SCRYPT_N,
        r=config.SCRYPT_R,
        p=config.SCRYPT_P,
        dklen=32,
    )
    return (
        f"scrypt${config.SCRYPT_N}${config.SCRYPT_R}${config.SCRYPT_P}"
        f"${salt.hex()}${digest.hex()}"
    )


def verify_password(password: str, stored: str | None) -> bool:
    if not stored:
        return False
    try:
        scheme, n, r, p, salt_hex, digest_hex = stored.split("$")
        if scheme != "scrypt":
            return False
        digest = hashlib.scrypt(
            password.encode("utf-8"),
            salt=bytes.fromhex(salt_hex),
            n=int(n),
            r=int(r),
            p=int(p),
            dklen=len(bytes.fromhex(digest_hex)),
        )
        return hmac.compare_digest(digest.hex(), digest_hex)
    except (ValueError, TypeError):
        return False


# ---------------------------------------------------------------------------
# Tokens and cookies
# ---------------------------------------------------------------------------

def new_token(nbytes: int = 32) -> str:
    return secrets.token_urlsafe(nbytes)


def token_digest(token: str) -> str:
    return hashlib.sha256(token.encode("utf-8")).hexdigest()


def _iso(value: datetime) -> str:
    return value.astimezone(timezone.utc).isoformat(timespec="seconds")


def session_expiry() -> str:
    return _iso(datetime.now(timezone.utc) + timedelta(days=config.AUTH_SESSION_DAYS))


def email_token_expiry(kind: str) -> str:
    if kind == "reset":
        delta = timedelta(minutes=config.AUTH_RESET_TTL_MINUTES)
    else:
        delta = timedelta(hours=config.AUTH_VERIFY_TTL_HOURS)
    return _iso(datetime.now(timezone.utc) + delta)


def public_user(row: dict) -> dict:
    """Strip password hashes before a user dict crosses the API boundary."""
    return {
        "id": row["id"],
        "email": row["email"],
        "name": row.get("name") or "",
        "provider": row.get("provider") or "email",
        "email_verified": int(row.get("email_verified") or 0),
        "created_at": row.get("created_at"),
        "last_login_at": row.get("last_login_at"),
    }


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for") or ""
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else "unknown"


async def create_session(user: dict, request: Request) -> str:
    token = new_token()
    await db.create_session(
        token_digest(token),
        user["id"],
        session_expiry(),
        (request.headers.get("user-agent") or "")[:300],
        client_ip(request),
    )
    await db.update_user_login(user["id"])
    return token


def set_session_cookie(response: Response, token: str) -> None:
    response.set_cookie(
        config.AUTH_COOKIE_NAME,
        token,
        max_age=config.AUTH_SESSION_DAYS * 86400,
        httponly=True,
        samesite="lax",
        secure=config.AUTH_COOKIE_SECURE,
        path="/",
    )


def clear_session_cookie(response: Response) -> None:
    response.delete_cookie(
        config.AUTH_COOKIE_NAME,
        path="/",
        httponly=True,
        samesite="lax",
        secure=config.AUTH_COOKIE_SECURE,
    )


def _unauthorized() -> HTTPException:
    return HTTPException(status_code=401, detail="请先登录")


async def current_user(request: Request) -> dict:
    """FastAPI dependency: resolve the session cookie to a public user dict."""
    token = request.cookies.get(config.AUTH_COOKIE_NAME)
    if not token:
        raise _unauthorized()
    row = await db.get_session_user(token_digest(token))
    if not row:
        raise _unauthorized()
    return public_user(row)


async def optional_user(request: Request) -> dict | None:
    try:
        return await current_user(request)
    except HTTPException:
        return None


# ---------------------------------------------------------------------------
# URLs
# ---------------------------------------------------------------------------

def public_base_url(request: Request) -> str:
    if config.PUBLIC_BASE_URL:
        return config.PUBLIC_BASE_URL
    return str(request.base_url).rstrip("/")


def safe_redirect(value: str | None) -> str:
    """Only allow same-site paths; auth pages themselves are not useful."""
    if not value or not value.startswith("/") or value.startswith("//"):
        return "/dashboard"
    if "\\" in value or "\n" in value or "\r" in value:
        return "/dashboard"
    if value.startswith(("/login", "/register", "/verify-email", "/password/")):
        return "/dashboard"
    return value


def verification_url(request: Request, token: str, email: str, redirect: str) -> str:
    query = urlencode(
        {"token": token, "email": email, "redirect": safe_redirect(redirect)}
    )
    return f"{public_base_url(request)}/verify-email?{query}"


def reset_url(request: Request, token: str, email: str) -> str:
    query = urlencode({"token": token, "email": email})
    return f"{public_base_url(request)}/password/reset?{query}"


def dev_links_enabled() -> bool:
    if config.AUTH_DEV_LINKS is None:
        return not mailer.is_configured()
    return bool(config.AUTH_DEV_LINKS)


# ---------------------------------------------------------------------------
# In-process rate limiting (single uvicorn worker)
# ---------------------------------------------------------------------------

class RateLimiter:
    def __init__(self) -> None:
        self._hits: dict[str, deque[float]] = defaultdict(deque)
        self._lock = asyncio.Lock()

    async def allow(self, key: str, limit: int, window_seconds: float) -> bool:
        now = time.monotonic()
        async with self._lock:
            bucket = self._hits[key]
            while bucket and bucket[0] <= now - window_seconds:
                bucket.popleft()
            if len(bucket) >= limit:
                return False
            bucket.append(now)
            return True

    async def reset(self, key: str) -> None:
        async with self._lock:
            self._hits.pop(key, None)


limiter = RateLimiter()


async def enforce_limit(key: str, limit: int, window_seconds: float) -> None:
    if not await limiter.allow(key, limit, window_seconds):
        raise HTTPException(status_code=429, detail="操作太频繁，请稍后再试")


# ---------------------------------------------------------------------------
# OAuth helpers
# ---------------------------------------------------------------------------

def google_configured() -> bool:
    return bool(config.GOOGLE_CLIENT_ID and config.GOOGLE_CLIENT_SECRET)


def google_enabled() -> bool:
    """Environment gate for the Google login entry (credentials aside)."""
    return config.AUTH_GOOGLE_ENABLED


def google_available() -> bool:
    """Google login can actually be offered: enabled and configured."""
    return google_enabled() and google_configured()


def google_disabled_reason() -> str | None:
    """User-facing explanation when Google login cannot be offered."""
    if not google_enabled():
        return config.AUTH_GOOGLE_DISABLED_REASON
    if not google_configured():
        return "Google 登录尚未配置，请使用邮箱登录。"
    return None


def google_redirect_uri(request: Request) -> str:
    if config.GOOGLE_REDIRECT_URI:
        return config.GOOGLE_REDIRECT_URI
    return f"{public_base_url(request)}/api/auth/google/callback"


def google_auth_url(request: Request, state: str) -> str:
    query = urlencode(
        {
            "client_id": config.GOOGLE_CLIENT_ID,
            "redirect_uri": google_redirect_uri(request),
            "response_type": "code",
            "scope": "openid email profile",
            "state": state,
            "access_type": "online",
            "prompt": "select_account",
        }
    )
    return f"https://accounts.google.com/o/oauth2/v2/auth?{query}"


def quote_email(email: str) -> str:
    return quote(email, safe="")


# ---------------------------------------------------------------------------
# One-time token issue helpers
# ---------------------------------------------------------------------------

async def issue_email_token(user: dict, kind: str) -> str:
    token = new_token()
    await db.create_email_token(
        token_digest(token),
        user["id"],
        kind,
        user["email"],
        email_token_expiry(kind),
    )
    return token
