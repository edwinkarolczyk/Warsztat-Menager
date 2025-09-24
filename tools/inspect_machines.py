import os
import sys

sys.path.append(".")

from utils_maszyny import LEGACY_DATA, PRIMARY_DATA, _index_by_id, _load_json_file


def dump(path: str) -> None:
    rows = _load_json_file(path)
    ids = [str(row.get("id") or row.get("nr_ewid") or "") for row in rows]
    ids_ok = [value for value in ids if value]
    missing = len(ids) - len(ids_ok)
    unique = len(_index_by_id(rows))

    print(f"\nFILE: {os.path.abspath(path)}")
    print(f"  records: {len(rows)}")
    print(f"  with id/nr_ewid: {len(ids_ok)} | missing id: {missing}")
    print(f"  unique id count: {unique}")
    print(f"  sample ids: {ids_ok[:10]}{' ...' if len(ids_ok) > 10 else ''}")


if __name__ == "__main__":
    dump(PRIMARY_DATA)
    dump(LEGACY_DATA)
