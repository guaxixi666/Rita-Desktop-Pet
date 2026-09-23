from __future__ import annotations

import logging
import random
from collections.abc import Callable
from datetime import datetime, time, timedelta, timezone

from codex_usage_pet.services.settings import AppSettings, SettingsStore

from .loader import SkinRepository
from .models import DEFAULT_SKIN_ID, SkinPack

LOGGER = logging.getLogger(__name__)


class SkinManager:
    def __init__(
        self,
        settings: AppSettings,
        store: SettingsStore,
        repository: SkinRepository | None = None,
        *,
        clock: Callable[[], datetime] | None = None,
        rng: random.Random | None = None,
    ) -> None:
        self.settings = settings
        self.store = store
        self.repository = repository or SkinRepository()
        self.clock = clock or (lambda: datetime.now(timezone.utc))
        self.rng = rng or random.Random()
        self.repository.scan()
        self.current = self._resolve_current()

    @property
    def packs(self) -> dict[str, SkinPack]:
        return self.repository.packs

    def rescan(self) -> SkinPack:
        self.repository.scan()
        self.current = self._resolve_current()
        return self.current

    def change(self, skin_id: str, *, reason: str = "manual", now: datetime | None = None) -> SkinPack | None:
        pack = self.packs.get(skin_id)
        if pack is None:
            return None
        changed = pack.id != self.current.id
        self.current = pack
        self.settings.current_skin = pack.id
        if changed:
            moment = _utc(now or self.clock())
            self.settings.last_skin_change = moment.isoformat()
            LOGGER.info("Skin changed: %s (%s)", pack.id, reason)
        self.store.save(self.settings)
        return pack

    def random_change(self, *, reason: str = "random", now: datetime | None = None) -> SkinPack:
        choices = list(self.packs.values())
        if self.settings.random_skin_no_repeat and len(choices) > 1:
            choices = [pack for pack in choices if pack.id != self.current.id]
        if not choices:
            return self.current
        chosen = self.rng.choice(choices)
        return self.change(chosen.id, reason=reason, now=now) or self.current

    def maybe_auto_change(self, now: datetime | None = None) -> SkinPack | None:
        if not self.settings.auto_skin_enabled:
            return None
        moment = _utc(now or self.clock())
        if not self._is_due(moment):
            return None
        LOGGER.info("Auto skin change: mode=%s", self.settings.auto_skin_mode)
        previous = self.current.id
        pack = self.random_change(reason="auto", now=moment)
        if pack.id == previous:
            # A single-pack installation has nothing to change to. Mark this
            # due check as handled so it does not retry every minute.
            self.settings.last_skin_change = moment.isoformat()
            self.store.save(self.settings)
        return pack

    def set_auto_interval(self, hours: int | None) -> None:
        if hours is None:
            self.settings.auto_skin_enabled = False
            self.settings.auto_skin_mode = "off"
        else:
            self.settings.auto_skin_enabled = True
            self.settings.auto_skin_mode = "interval"
            self.settings.auto_skin_interval_hours = max(1, min(24 * 30, int(hours)))
            if _parse_timestamp(self.settings.last_skin_change) is None:
                self.settings.last_skin_change = _utc(self.clock()).isoformat()
        self.store.save(self.settings)

    def set_auto_fixed_time(self, value: str) -> None:
        _parse_fixed_time(value)
        self.settings.auto_skin_enabled = True
        self.settings.auto_skin_mode = "fixed_time"
        self.settings.auto_skin_fixed_time = value
        if _parse_timestamp(self.settings.last_skin_change) is None:
            self.settings.last_skin_change = _utc(self.clock()).isoformat()
        self.store.save(self.settings)

    def _resolve_current(self) -> SkinPack:
        pack = self.repository.packs.get(self.settings.current_skin)
        if pack is None:
            pack = self.repository.packs.get(DEFAULT_SKIN_ID) or self.repository.default()
            self.settings.current_skin = pack.id
            self.store.save(self.settings)
        return pack

    def _is_due(self, now_utc: datetime) -> bool:
        last = _parse_timestamp(self.settings.last_skin_change)
        if last is None:
            self.settings.last_skin_change = now_utc.isoformat()
            self.store.save(self.settings)
            return False
        if now_utc < last:
            return False
        if self.settings.auto_skin_mode == "interval":
            return now_utc - last >= timedelta(hours=self.settings.auto_skin_interval_hours)
        if self.settings.auto_skin_mode == "fixed_time":
            local_now = now_utc.astimezone()
            fixed = _parse_fixed_time(self.settings.auto_skin_fixed_time)
            latest = datetime.combine(local_now.date(), fixed, tzinfo=local_now.tzinfo)
            if latest > local_now:
                latest -= timedelta(days=1)
            return last < latest.astimezone(timezone.utc) <= now_utc
        return False


def _utc(value: datetime) -> datetime:
    if value.tzinfo is None:
        return value.astimezone().astimezone(timezone.utc)
    return value.astimezone(timezone.utc)


def _parse_timestamp(value: str | None) -> datetime | None:
    if not value:
        return None
    try:
        parsed = datetime.fromisoformat(value)
    except (TypeError, ValueError):
        return None
    return _utc(parsed)


def _parse_fixed_time(value: str) -> time:
    try:
        parsed = datetime.strptime(value, "%H:%M")
    except (TypeError, ValueError) as exc:
        raise ValueError("fixed skin time must use HH:MM") from exc
    return parsed.time()
