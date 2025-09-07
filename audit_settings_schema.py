import json
from pathlib import Path


def main() -> None:
    schema_path = Path("settings_schema.json")
    schema = json.loads(schema_path.read_text(encoding="utf-8"))
    tabs = schema.get("tabs", [])
    print(f"schema tabs: {len(tabs)}")
    missing_keys = []
    type_mismatches = []
    for tab in tabs:
        groups = tab.get("groups")
        if groups is None:
            missing_keys.append(tab.get("id", "<unknown>"))
        elif not isinstance(groups, list):
            type_mismatches.append(tab.get("id", "<unknown>"))
    print(f"missing_keys: {missing_keys}")
    print(f"type_mismatches: {type_mismatches}")


if __name__ == "__main__":
    main()
