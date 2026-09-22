from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from decimal import Decimal, InvalidOperation
from typing import Any


def _clamp_percent(value: Any) -> float:
    try:
        number = float(value)
    except (TypeError, ValueError):
        number = 0.0
    return max(0.0, min(100.0, number))


def local_datetime_from_epoch(value: Any) -> datetime | None:
    if value is None:
        return None
    try:
        timestamp = float(value)
    except (TypeError, ValueError):
        return None
    if timestamp > 10_000_000_000:
        timestamp /= 1000.0
    try:
        return datetime.fromtimestamp(timestamp).astimezone()
    except (OSError, OverflowError, ValueError):
        return None


@dataclass(frozen=True, slots=True)
class UsageWindow:
    used_percent: float
    window_duration_mins: int | None = None
    resets_at: datetime | None = None

    @property
    def remaining_percent(self) -> float:
        return 100.0 - _clamp_percent(self.used_percent)


@dataclass(frozen=True, slots=True)
class Credits:
    balance: Decimal | None = None
    has_credits: bool = False
    unlimited: bool = False

    @classmethod
    def from_payload(cls, payload: dict[str, Any] | None) -> "Credits | None":
        if not payload:
            return None
        raw_balance = payload.get("balance")
        balance = None
        if raw_balance not in (None, ""):
            try:
                balance = Decimal(str(raw_balance))
            except InvalidOperation:
                balance = None
        return cls(
            balance=balance,
            has_credits=bool(payload.get("hasCredits", False)),
            unlimited=bool(payload.get("unlimited", False)),
        )


@dataclass(frozen=True, slots=True)
class AccountInfo:
    account_type: str | None = None
    plan_type: str | None = None


@dataclass(frozen=True, slots=True)
class UsageSnapshot:
    five_hour: UsageWindow | None = None
    weekly: UsageWindow | None = None
    credits: Credits | None = None
    reset_credits_available: int | None = None
    account: AccountInfo = AccountInfo()
    limit_id: str | None = None

    @property
    def remaining_percent(self) -> float | None:
        values = [
            window.remaining_percent
            for window in (self.five_hour, self.weekly)
            if window is not None
        ]
        return min(values) if values else None


@dataclass(frozen=True, slots=True)
class UsageResult:
    snapshot: UsageSnapshot | None
    error: str | None = None

    @property
    def available(self) -> bool:
        return self.snapshot is not None and self.error is None

