from __future__ import annotations

import json

import settings_tutorial_runtime as tutorial_settings
from gui_samouczek import CONTENT_PATH, CURRENT_WM_VERSION, load_tutorial


def test_tutorial_payload_has_steps() -> None:
    data = load_tutorial(CONTENT_PATH)
    slides = data.get("slides")
    assert isinstance(slides, list)
    assert slides
    assert all(isinstance(slide, dict) for slide in slides)
    assert all(isinstance(slide.get("steps"), list) for slide in slides)


def test_tutorial_metadata_matches_wm_version() -> None:
    raw = json.loads(CONTENT_PATH.read_text(encoding="utf-8"))
    assert raw.get("wm_version") == CURRENT_WM_VERSION
    assert isinstance(raw.get("updated"), str)
    assert len(raw["updated"]) == 10

    loaded = load_tutorial(CONTENT_PATH)
    assert loaded.get("wm_version") == CURRENT_WM_VERSION


def test_tutorial_settings_are_separate_and_roundtrip(tmp_path, monkeypatch) -> None:
    settings_path = tmp_path / "samouczek" / "ustawienia.json"
    monkeypatch.setattr(tutorial_settings, "SETTINGS_PATH", settings_path)

    assert tutorial_settings.is_tutorial_button_enabled() is True

    tutorial_settings.set_tutorial_button_enabled(False)
    assert tutorial_settings.is_tutorial_button_enabled() is False
    payload = json.loads(settings_path.read_text(encoding="utf-8"))
    assert payload == {"show_tutorial_button": False}

    tutorial_settings.set_tutorial_button_enabled(True)
    assert tutorial_settings.is_tutorial_button_enabled() is True
