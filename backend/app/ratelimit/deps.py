"""Rate-limit dependencies for routes.

Limiters are process-wide singletons built lazily from settings, so every
request for a given scope shares one window.
"""

from __future__ import annotations

import logging

from fastapi import Depends, Request

from app.config import Settings, get_settings
from app.errors import RateLimited
from app.ratelimit.limiter import FailureTracker, SlidingWindowLimiter

logger = logging.getLogger(__name__)

_limiters: dict[str, SlidingWindowLimiter] = {}
_trackers: dict[str, FailureTracker] = {}


def _limiter(name: str, limit: int, window: int) -> SlidingWindowLimiter:
    existing = _limiters.get(name)
    if existing is None or existing.limit != limit or existing.window != window:
        existing = SlidingWindowLimiter(limit, window, name=name)
        _limiters[name] = existing
    return existing


def login_failures(settings: Settings) -> FailureTracker:
    """Per-account consecutive-failure tracker for sign-in.

    Rebuilt when the configured thresholds change, matching `_limiter`. A
    cached tracker that ignored later settings would silently keep enforcing
    whichever values happened to be live on first use.
    """
    tracker = _trackers.get("login")
    if (
        tracker is None
        or tracker.threshold != settings.lockout_threshold
        or tracker.base != settings.lockout_base_seconds
        or tracker.max_seconds != settings.lockout_max_seconds
    ):
        tracker = FailureTracker(
            threshold=settings.lockout_threshold,
            base_seconds=settings.lockout_base_seconds,
            max_seconds=settings.lockout_max_seconds,
            name="login",
        )
        _trackers["login"] = tracker
    return tracker


def reset_all() -> None:
    """Clear every limiter. Used between tests; never called in production."""
    for limiter in _limiters.values():
        limiter.reset()
    for tracker in _trackers.values():
        tracker.reset()


_warned_about_proxy_headers = False


def client_ip(request: Request, settings: Settings) -> str:
    """The address to attribute a request to.

    X-Forwarded-For is only honoured when `trust_proxy_headers` is on. Any
    client can send that header, so trusting it without a proxy in front that
    overwrites it would let an attacker give itself a fresh identity per
    request and bypass every per-IP limit here.

    When trusted, the *left-most* entry is used: that is the original client,
    with each proxy appending its own peer to the right.

    The check below exists because this setting can be silently overruled.
    Uvicorn's own `proxy_headers` option defaults to True and rewrites
    `request.client` from X-Forwarded-For before any application code runs, so
    `trust_proxy_headers=False` alone does NOT stop header spoofing. Run the
    server through `backend/run.py`, which wires uvicorn's setting to this one.
    """
    global _warned_about_proxy_headers

    forwarded = request.headers.get("x-forwarded-for")
    peer = request.client.host if request.client else "unknown"

    if settings.trust_proxy_headers:
        if forwarded:
            first = forwarded.split(",")[0].strip()
            if first:
                return first
        return peer

    if forwarded and not _warned_about_proxy_headers:
        claimed = forwarded.split(",")[0].strip()
        if claimed and claimed == peer:
            _warned_about_proxy_headers = True
            logger.error(
                "trust_proxy_headers is off, but the connection address (%s) "
                "matches the X-Forwarded-For header, which means the server "
                "is rewriting it. Per-IP rate limits can be bypassed by "
                "spoofing that header. Start the API with backend/run.py, or "
                "pass --no-proxy-headers to uvicorn.",
                peer,
            )

    return peer


def _enforce(request: Request, settings: Settings, scope: str, limit: int, window: int) -> None:
    if not settings.rate_limit_enabled:
        return
    key = f"{scope}:{client_ip(request, settings)}"
    decision = _limiter(scope, limit, window).check(key)
    if not decision.allowed:
        raise RateLimited(
            decision.retry_after,
            "Too many attempts from this address. "
            f"Try again in {decision.retry_after} seconds.",
        )


def limit_login(
    request: Request, settings: Settings = Depends(get_settings)
) -> None:
    _enforce(
        request,
        settings,
        "login",
        settings.login_attempts_per_ip,
        settings.login_window_seconds,
    )


def limit_signup(
    request: Request, settings: Settings = Depends(get_settings)
) -> None:
    _enforce(
        request,
        settings,
        "signup",
        settings.signup_attempts_per_ip,
        settings.signup_window_seconds,
    )


def limit_upload_for(user_id: str, settings: Settings) -> None:
    """Per-account cap on analyses.

    Keyed by account rather than address because an analysis costs real money
    once a model provider is configured, and the account is the thing being
    billed.
    """
    if not settings.rate_limit_enabled:
        return
    decision = _limiter(
        "upload", settings.upload_per_user, settings.upload_window_seconds
    ).check(f"upload:{user_id}")
    if not decision.allowed:
        raise RateLimited(
            decision.retry_after,
            "You have reached the analysis limit for now. "
            f"Try again in {max(1, decision.retry_after // 60)} minute(s).",
        )
