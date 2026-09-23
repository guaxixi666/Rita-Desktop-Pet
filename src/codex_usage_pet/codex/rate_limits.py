from __future__ import annotations

from typing import Any

from .models import (
    AccountInfo,
    Credits,
    UsageSnapshot,
    UsageWindow,
    local_datetime_from_epoch,
)

WEEK_MINUTES = 7 * 24 * 60
DEFAULT_LIMIT_ID = "codex"


class RateLimitParseError(ValueError):
    pass


def parse_account(payload: dict[str, Any] | None) -> AccountInfo:
    account = (payload or {}).get("account") or {}
    return AccountInfo(
        account_type=_optional_text(account.get("type")),
        plan_type=_optional_text(account.get("planType")),
    )


def parse_rate_limits(
    payload: dict[str, Any], account: AccountInfo | None = None
) -> UsageSnapshot:
    if not isinstance(payload, dict):
        raise RateLimitParseError("rate-limit response is not an object")
    snapshot, limit_id = _pick_snapshot(payload)
    primary = _parse_window(snapshot.get("primary"))
    secondary = _parse_window(snapshot.get("secondary"))

    five_hour, weekly = _classify_windows(primary, secondary)

    if five_hour is None and weekly is None:
        raise RateLimitParseError("response contains no usable rate-limit windows")

    plan_type = _optional_text(snapshot.get("planType"))
    resolved_account = account or AccountInfo()
    if plan_type and not resolved_account.plan_type:
        resolved_account = AccountInfo(resolved_account.account_type, plan_type)

    reset_summary = payload.get("rateLimitResetCredits") or {}
    reset_count = reset_summary.get("availableCount")
    if not isinstance(reset_count, int):
        reset_count = None

    return UsageSnapshot(
        five_hour=five_hour,
        weekly=weekly,
        credits=Credits.from_payload(snapshot.get("credits")),
        reset_credits_available=reset_count,
        account=resolved_account,
        limit_id=_optional_text(snapshot.get("limitId")) or limit_id,
    )


def _pick_snapshot(payload: dict[str, Any]) -> tuple[dict[str, Any], str | None]:
    buckets = payload.get("rateLimitsByLimitId")
    if isinstance(buckets, dict) and buckets:
        preferred = buckets.get(DEFAULT_LIMIT_ID)
        if isinstance(preferred, dict):
            return preferred, DEFAULT_LIMIT_ID
        for limit_id, candidate in buckets.items():
            if isinstance(candidate, dict) and candidate.get("limitId") in (None, DEFAULT_LIMIT_ID):
                return candidate, str(limit_id)
    legacy = payload.get("rateLimits")
    if isinstance(legacy, dict) and legacy:
        return legacy, _optional_text(legacy.get("limitId"))
    raise RateLimitParseError("response contains no Codex rate-limit snapshot")


def _parse_window(payload: Any) -> UsageWindow | None:
    if not isinstance(payload, dict) or "usedPercent" not in payload:
        return None
    try:
        used = max(0.0, min(100.0, float(payload["usedPercent"])))
    except (TypeError, ValueError) as exc:
        raise RateLimitParseError("usedPercent is not numeric") from exc
    duration = payload.get("windowDurationMins")
    try:
        duration = int(duration) if duration is not None else None
    except (TypeError, ValueError):
        duration = None
    return UsageWindow(
        used_percent=used,
        window_duration_mins=duration,
        resets_at=local_datetime_from_epoch(payload.get("resetsAt")),
    )


def _classify_windows(
    primary: UsageWindow | None, secondary: UsageWindow | None
) -> tuple[UsageWindow | None, UsageWindow | None]:
    """Map windows by their duration while preserving legacy field order."""
    windows = [window for window in (primary, secondary) if window is not None]
    weekly = next(
        (
            window
            for window in windows
            if window.window_duration_mins is not None
            and window.window_duration_mins >= WEEK_MINUTES
        ),
        None,
    )
    if weekly is not None:
        five_hour = next((window for window in windows if window is not weekly), None)
        return five_hour, weekly
    return primary, secondary


def _optional_text(value: Any) -> str | None:
    return str(value) if value not in (None, "") else None

