import json
from pathlib import Path


def load_json(path: Path):
    with path.open(encoding="utf-8") as f:
        return json.load(f)


def extract_fields(obj):
    fields = []
    if isinstance(obj, dict):
        if "key" in obj and "type" in obj:
            fields.append(obj)
        for value in obj.values():
            fields.extend(extract_fields(value))
    elif isinstance(obj, list):
        for item in obj:
            fields.extend(extract_fields(item))
    return fields


def get_value(config, key):
    current = config
    for part in key.split("."):
        if isinstance(current, dict) and part in current:
            current = current[part]
        else:
            return None
    return current


def check_value(field, value):
    mismatches = []
    key = field["key"]
    ftype = field["type"]
    if value is None:
        mismatches.append(f"{key}: missing in config")
        return mismatches
    if ftype == "enum":
        allowed = field.get("values", [])
        if value not in allowed:
            mismatches.append(f"{key}: {value!r} not in enum {allowed}")
        return mismatches
    type_map = {
        "bool": bool,
        "int": int,
        "array": list,
        "string": str,
        "path": str,
    }
    expected = type_map.get(ftype)
    if expected and not isinstance(value, expected):
        mismatches.append(
            f"{key}: expected {expected.__name__}, got {type(value).__name__}"
        )
    if ftype == "array" and isinstance(value, list):
        vtype = field.get("value_type")
        item_type = type_map.get(vtype)
        if item_type:
            for idx, item in enumerate(value):
                if not isinstance(item, item_type):
                    mismatches.append(
                        f"{key}[{idx}]: expected {item_type.__name__}, got {type(item).__name__}"
                    )
    return mismatches


def main():
    schema = load_json(Path("settings_schema.json"))
    config = load_json(Path("config.json"))
    fields = extract_fields(schema)
    errors = []
    for field in fields:
        value = get_value(config, field["key"])
        errors.extend(check_value(field, value))
    if errors:
        print("\n".join(errors))
    else:
        print("All config values match schema")


if __name__ == "__main__":
    main()
