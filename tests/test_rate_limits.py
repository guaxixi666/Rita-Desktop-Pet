from __future__ import annotations

from datetime import datetime
from decimal import Decimal

import pytest

from codex_usage_pet.codex.models import local_datetime_from_epoch
from codex_usage_pet.codex.rate_limits import (
    RateLimitParseError,
    parse_account,
    parse_rate_limits,
)


def payload(used_5h: int = 28, used_weekly: int = 39) -> dict:
    return {
        "rateLimits": {
            "limitId": "codex",
            "planType": "plus",
            "credits": {"balance": "320", "hasCredits": True, "unlimited": False},
            "primary": {
                "usedPercent": used_5h,
                "windowDurationMins": 300,
                "resetsAt": 1_800_000_000,
            },
            "secondary": {
                "usedPercent": used_weekly,
                "windowDurationMins": 10080,
                "resetsAt": 1_800_500_000,
            },
        },
        "rateLimitResetCredits": {"availableCount": 2},
    }


def test_parses_5h_weekly_remaining_reset_and_credits() -> None:
    result = parse_rate_limits(payload(), parse_account({"account": {"type": "chatgpt"}}))
    assert result.five_hour is not None
    assert result.weekly is not None
    assert result.five_hour.used_percent == 28
    assert result.five_hour.remaining_percent == 72
    assert result.weekly.remaining_percent == 61
    assert result.five_hour.resets_at is not None
    assert result.five_hour.resets_at.tzinfo is not None
    assert result.credits is not None
    assert result.credits.balance == Decimal("320")
    assert result.reset_credits_available == 2


@pytest.mark.parametrize(("used", "remaining"), [(0, 100), (100, 0), (-5, 100), (120, 0)])
def test_remaining_percent_is_not_reversed(used: int, remaining: int) -> None:
    result = parse_rate_limits(payload(used_5h=used))
    assert result.five_hour is not None
    assert result.five_hour.remaining_percent == remaining


def test_prefers_codex_multi_bucket() -> None:
    data = payload()
    data["rateLimitsByLimitId"] = {
        "codex_other": {"limitId": "codex_other", "primary": {"usedPercent": 99}},
        "codex": data["rateLimits"],
    }
    result = parse_rate_limits(data)
    assert result.limit_id == "codex"
    assert result.five_hour is not None
    assert result.five_hour.used_percent == 28


def test_single_week_window_maps_to_weekly() -> None:
    result = parse_rate_limits(
        {
            "rateLimits": {
                "primary": {"usedPercent": 42, "windowDurationMins": 10080}
            }
        }
    )
    assert result.five_hour is None
    assert result.weekly is not None
    assert result.weekly.remaining_percent == 58


def test_reversed_server_window_order_maps_by_duration() -> None:
    result = parse_rate_limits(
        {
            "rateLimits": {
                "primary": {"usedPercent": 40, "windowDurationMins": 10080},
                "secondary": {"usedPercent": 20, "windowDurationMins": 300},
            }
        }
    )
    assert result.five_hour is not None
    assert result.weekly is not None
    assert result.five_hour.used_percent == 20
    assert result.weekly.used_percent == 40


@pytest.mark.parametrize("bad", [{}, {"rateLimits": {}}, {"rateLimits": {"primary": {}}}])
def test_missing_fields_raise_clear_error(bad: dict) -> None:
    with pytest.raises(RateLimitParseError):
        parse_rate_limits(bad)


def test_millisecond_epoch_is_supported() -> None:
    seconds = local_datetime_from_epoch(1_800_000_000)
    millis = local_datetime_from_epoch(1_800_000_000_000)
    assert isinstance(seconds, datetime)
    assert seconds == millis

