from pathlib import Path

from codex_usage_pet.services.settings import AppSettings, SettingsStore


def test_missing_config_uses_defaults(tmp_path: Path) -> None:
    loaded = SettingsStore(tmp_path / "missing.json").load()
    assert loaded == AppSettings()


def test_invalid_config_uses_defaults(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text("not json", encoding="utf-8")
    assert SettingsStore(path).load() == AppSettings()


def test_round_trip_and_normalization(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    store = SettingsStore(path)
    store.save(AppSettings(window_x=20, opacity=5, refresh_interval=1, locked=True))
    loaded = store.load()
    assert loaded.window_x == 20
    assert loaded.opacity == 1.0
    assert loaded.refresh_interval == 30
    assert loaded.locked is True


def test_unknown_config_fields_are_ignored(tmp_path: Path) -> None:
    path = tmp_path / "config.json"
    path.write_text('{"opacity": 0.7, "token": "must-not-be-used"}', encoding="utf-8")
    assert SettingsStore(path).load().opacity == 0.7

