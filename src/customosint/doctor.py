"""Local environment diagnostics without changing the system."""

from __future__ import annotations

import os
import shutil
import socket
import sys
from pathlib import Path


def checks() -> list[tuple[str, str, str]]:
    result = [("Python", "READY" if sys.version_info >= (3, 10) else "OLD", sys.version.split()[0]), ("venv", "READY" if sys.prefix != sys.base_prefix else "WARN", "active" if sys.prefix != sys.base_prefix else "not active")]
    for label, command in (("Maigret", "maigret"), ("Sherlock", "sherlock"), ("Holehe", "holehe"), ("SpiderFoot", "sf.py"), ("GHunt", "ghunt"), ("ExifTool", "exiftool"), ("Neo4j", "cypher-shell")):
        path = shutil.which(command); result.append((label, "READY" if path else "MISSING", path or f"install {command}"))
    for label, variable in (("HIBP API", "HIBP_API_KEY"), ("GitHub API", "GITHUB_TOKEN")):
        result.append((label, "READY" if os.getenv(variable) else "NO API KEY", variable))
    writable = os.access(Path.cwd(), os.W_OK); result.append(("Filesystem", "READY" if writable else "ERROR", str(Path.cwd())))
    try:
        with socket.create_connection(("github.com", 443), timeout=3):
            result.append(("Network", "READY", "github.com:443"))
    except OSError as exc:
        result.append(("Network", "WARN", f"github.com:443 unavailable: {exc}"))
    return result
