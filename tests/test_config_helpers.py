import pytest

from config_manager import deep_merge, flatten, get_by_key, set_by_key


def test_deep_merge_nested_and_preserves_original():
    a = {"a": {"x": 1}, "b": 2}
    b = {"a": {"y": 3}, "c": 4}
    merged = deep_merge(a, b)
    assert merged == {"a": {"x": 1, "y": 3}, "b": 2, "c": 4}
    # ensure original dict not mutated
    assert a == {"a": {"x": 1}, "b": 2}


def test_deep_merge_overwrites_non_dict_values():
    a = {"a": {"x": 1}}
    b = {"a": 2}
    assert deep_merge(a, b) == {"a": 2}


def test_flatten_nested_structure_and_prefix():
    data = {"a": {"b": {"c": 1}}, "d": 2}
    assert flatten(data) == {"a.b.c": 1, "d": 2}
    assert flatten({"a": {"b": 1}}, prefix="root") == {"root.a.b": 1}
    assert flatten({}, prefix="ignored") == {}


def test_get_by_key_retrieves_and_handles_missing():
    data = {"a": {"b": {"c": 1}}, "d": 2}
    assert get_by_key(data, "a.b.c") == 1
    assert get_by_key(data, "a.b.x", "default") == "default"
    # Path hits non-dict value
    assert get_by_key(data, "d.x", "missing") == "missing"


def test_set_by_key_creates_path_and_overwrites():
    data = {}
    set_by_key(data, "a.b.c", 1)
    assert data == {"a": {"b": {"c": 1}}}

    # Overwrite non-dict with dict on the path
    data = {"a": 1}
    set_by_key(data, "a.b", 2)
    assert data == {"a": {"b": 2}}

    # Overwrite existing leaf value
    set_by_key(data, "a.b", 3)
    assert data == {"a": {"b": 3}}
