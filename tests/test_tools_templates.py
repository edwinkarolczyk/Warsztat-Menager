import json
from pathlib import Path

import pytest

import tools_templates


@pytest.fixture
def template_factory(tmp_path: Path):
    def _create(name: str, ident: str, collection: str = "col") -> Path:
        col_dir = tmp_path / collection
        col_dir.mkdir(exist_ok=True)
        path = col_dir / name
        path.write_text(json.dumps({"id": ident}, indent=2), encoding="utf-8")
        return path

    return _create


def test_limit_8x8(template_factory) -> None:
    paths = [
        template_factory(f"{i:03}.json", f"{i:03}")
        for i in range(tools_templates.MAX_TEMPLATES + 1)
    ]
    with pytest.raises(ValueError):
        tools_templates.load_templates(paths)


def test_duplicate_detection(template_factory) -> None:
    p1 = template_factory("a.json", "01")
    p2 = template_factory("b.json", "01")
    with pytest.raises(ValueError):
        tools_templates.load_templates([p1, p2])


def test_missing_file_is_ignored(tmp_path: Path) -> None:
    missing = tmp_path / "col" / "missing.json"
    result = tools_templates.load_templates([missing])
    assert result == []
