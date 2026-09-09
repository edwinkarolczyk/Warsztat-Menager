from __future__ import annotations

import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from narzedzia_ui import editor_variant_runtime as gallery


class ToolsEditorGalleryTests(unittest.TestCase):
    def setUp(self) -> None:
        self.temp_dir = tempfile.TemporaryDirectory()
        self.base = Path(self.temp_dir.name)
        (self.base / "media").mkdir()

    def tearDown(self) -> None:
        self.temp_dir.cleanup()

    def _window(self, values: list[str]) -> SimpleNamespace:
        return SimpleNamespace(
            _wm_tool_images_get=lambda: list(values),
            _wm_tool_dxf_preview_get=lambda: "",
        )

    def test_live_gallery_uses_every_image_before_json_save(self) -> None:
        values = []
        for index in range(1, 6):
            relative = f"media/010_img{index}.jpg"
            (self.base / relative).write_bytes(b"image")
            values.append(relative)
        window = self._window(values)

        with patch.object(gallery, "_media_base", return_value=self.base), patch.object(
            gallery,
            "_current_doc",
            side_effect=AssertionError("JSON must not be read for a live editor gallery"),
        ):
            items = gallery._preview_items(window)

        self.assertEqual([item[0] for item in items], values)
        self.assertEqual(gallery._images_summary(values), "5 plików")

    def test_empty_live_gallery_does_not_restore_saved_photo(self) -> None:
        old_photo = self.base / "media" / "old.jpg"
        old_photo.write_bytes(b"old")
        window = self._window([])

        with patch.object(gallery, "_media_base", return_value=self.base), patch.object(
            gallery, "_current_doc", return_value={"obrazy": ["media/old.jpg"]}
        ):
            items = gallery._preview_items(window)

        self.assertEqual(items, [])

    def test_missing_image_stays_visible_as_repairable_gallery_item(self) -> None:
        window = self._window(["media/missing.jpg"])

        with patch.object(gallery, "_media_base", return_value=self.base):
            items = gallery._preview_items(window)

        self.assertEqual(len(items), 1)
        self.assertEqual(items[0][0], "media/missing.jpg")
        self.assertEqual(items[0][2], "missing_image")

    def test_windows_separator_resolves_on_every_platform(self) -> None:
        photo = self.base / "media" / "photo.jpg"
        photo.write_bytes(b"image")
        window = self._window([r"media\photo.jpg"])

        with patch.object(gallery, "_media_base", return_value=self.base):
            items = gallery._preview_items(window)

        self.assertEqual(items[0][1], photo)
        self.assertEqual(items[0][2], "image")

    def test_dashboard_prefers_the_saved_added_date_key(self) -> None:
        self.assertEqual(
            gallery._added_date(
                {
                    "data_dodania": "2026-08-29 10:00",
                    "data": "wrong fallback",
                }
            ),
            "2026-08-29 10:00",
        )

    def test_gallery_navigation_wraps_in_both_directions(self) -> None:
        values = ["media/one.jpg", "media/two.jpg", "media/three.jpg"]
        for value in values:
            (self.base / value).write_bytes(b"image")
        window = self._window(values)

        with patch.object(gallery, "_media_base", return_value=self.base):
            self.assertEqual(gallery._step_gallery(window, -1), 2)
            self.assertEqual(gallery._preview_path(window), self.base / values[2])
            self.assertEqual(gallery._step_gallery(window, 1), 0)
            self.assertEqual(gallery._preview_path(window), self.base / values[0])


if __name__ == "__main__":
    unittest.main()
