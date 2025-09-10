import json
from pathlib import Path
from typing import Any, Dict


def _flatten_dict(data: Dict[str, Any], prefix: str = "") -> Dict[str, Any]:
    """Return a flattened dict using dot notation for nested keys."""
    items: Dict[str, Any] = {}
    for key, value in data.items():
        full_key = f"{prefix}.{key}" if prefix else key
        if isinstance(value, dict):
            items.update(_flatten_dict(value, full_key))
        else:
            items[full_key] = value
    return items


def _extract_schema_fields(schema: Dict[str, Any]) -> Dict[str, str]:
    """Extract mapping of field keys to types from settings schema."""
    fields: Dict[str, str] = {}
    for tab in schema.get("tabs", []):
        groups = tab.get("groups")
        if not isinstance(groups, list):
            continue
        for group in groups:
            for field in group.get("fields", []):
                key = field.get("key")
                field_type = field.get("type")
                if key and field_type:
                    fields[key] = field_type
    return fields


def main() -> None:
    schema_path = Path("settings_schema.json")
    config_path = Path("config.json")

    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    config = json.loads(config_path.read_text(encoding="utf-8"))

    schema_fields = _extract_schema_fields(schema)
    config_flat = _flatten_dict(config)

    missing_in_schema = []
    missing_in_config = []
    type_mismatches = []

    type_mapping: Dict[str, type] = {
        "bool": bool,
        "int": int,
        "string": str,
        "enum": str,
        "array": list,
    }

    def value_type(value: Any) -> str:
        if isinstance(value, bool):
            return "bool"
        if isinstance(value, int) and not isinstance(value, bool):
            return "int"
        if isinstance(value, list):
            return "array"
        if isinstance(value, str):
            return "string"
        return type(value).__name__

    for key, value in config_flat.items():
        if key not in schema_fields:
            missing_in_schema.append(key)
            continue
        expected = schema_fields[key]
        python_type = type_mapping.get(expected)
        if python_type and not (
            isinstance(value, python_type) and not (expected == "int" and isinstance(value, bool))
        ):
            type_mismatches.append(
                f"{key}: expected {expected}, got {value_type(value)}"
            )

    for key in schema_fields:
        if key not in config_flat:
            missing_in_config.append(key)

    report_lines = [
        "Missing keys in schema: "
        + (", ".join(missing_in_schema) if missing_in_schema else "None"),
        "Missing keys in config: "
        + (", ".join(missing_in_config) if missing_in_config else "None"),
        "Type mismatches: "
        + (", ".join(type_mismatches) if type_mismatches else "None"),
    ]

    report_path = Path("audit_settings_schema_report.txt")
    report_path.write_text("\n".join(report_lines) + "\n", encoding="utf-8")


if __name__ == "__main__":
    main()
