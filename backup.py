from __future__ import annotations

import base64
import os
from urllib.parse import urljoin
import urllib.request

from config_manager import ConfigManager


def upload_backup(local_path: str) -> bool:
    """Upload backup file to WebDAV folder specified in config.

    The configuration uses keys under ``backup.cloud``:
    - ``url`` – base URL of the WebDAV server
    - ``username`` – optional username
    - ``password`` – optional password
    - ``folder`` – target folder on the server

    Parameters
    ----------
    local_path:
        Path to the file that should be uploaded.

    Returns
    -------
    bool
        ``True`` on success, ``False`` otherwise.
    """
    cfg = ConfigManager()
    base_url = cfg.get("backup.cloud.url", "").rstrip("/")
    user = cfg.get("backup.cloud.username", "")
    password = cfg.get("backup.cloud.password", "")
    remote_folder = cfg.get("backup.cloud.folder", "").strip("/")

    if not base_url or not remote_folder:
        return False

    filename = os.path.basename(local_path)
    target_url = urljoin(f"{base_url}/", f"{remote_folder}/{filename}")

    with open(local_path, "rb") as fh:
        data = fh.read()

    req = urllib.request.Request(target_url, data=data, method="PUT")
    if user or password:
        token = base64.b64encode(f"{user}:{password}".encode("utf-8")).decode("ascii")
        req.add_header("Authorization", f"Basic {token}")

    try:
        with urllib.request.urlopen(req) as resp:  # type: ignore[call-arg]
            return 200 <= resp.status < 300
    except Exception:
        return False
