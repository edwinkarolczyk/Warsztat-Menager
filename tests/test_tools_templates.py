import json
from pathlib import Path

import pytest

import tools_templates


def _write_template(path: Path, ident: str) -> None:
    path.write_text(json.dumps({"id": ident}), encoding="utf-8")


def test_limit_8x8(tmp_path: Path) -> None:
    paths = []
    for i in range(tools_templates.MAX_TEMPLATES + 1):
        p = tmp_path / f"{i:03}.json"
        _write_template(p, f"{i:03}")
        paths.append(p)
    with pytest.raises(ValueError):
        tools_templates.load_templates(paths)


def test_duplicate_detection(tmp_path: Path) -> None:
    p1 = tmp_path / "a.json"
    p2 = tmp_path / "b.json"
    _write_template(p1, "01")
    _write_template(p2, "01")
    with pytest.raises(ValueError):
        tools_templates.load_templates([p1, p2])


def test_missing_file_is_ignored(tmp_path: Path) -> None:
    missing = tmp_path / "missing.json"
    result = tools_templates.load_templates([missing])
    assert result == []
