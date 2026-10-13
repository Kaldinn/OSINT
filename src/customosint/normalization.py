"""Canonical input normalization and safe seed derivation."""

from __future__ import annotations

import re
import unicodedata
from pathlib import Path
from urllib.parse import urlsplit, urlunsplit

EMAIL_RE = re.compile(r"^[A-Z0-9.!#$%&'*+/=?^_`{|}~-]+@[A-Z0-9.-]+\.[A-Z]{2,63}$", re.I)
USERNAME_RE = re.compile(r"^[\w.@+-]{1,128}$", re.UNICODE)


def normalize_email(value: str) -> str:
    value = value.strip().lower()
    if not EMAIL_RE.fullmatch(value):
        raise ValueError(f"Invalid email address: {value!r}")
    local, domain = value.rsplit("@", 1)
    return f"{local}@{domain.encode('idna').decode('ascii')}"


def normalize_username(value: str) -> str:
    value = unicodedata.normalize("NFKC", value).strip().lstrip("@").casefold()
    if not USERNAME_RE.fullmatch(value):
        raise ValueError(f"Invalid username: {value!r}")
    return value


def normalize_phone(value: str, default_country: str = "PL") -> str:
    raw = value.strip()
    digits = re.sub(r"\D", "", raw)
    if raw.startswith("+"):
        result = f"+{digits}"
    elif default_country.upper() == "PL" and len(digits) == 9:
        result = f"+48{digits}"
    elif digits.startswith("00"):
        result = f"+{digits[2:]}"
    else:
        raise ValueError("Phone requires a country code or a supported default country")
    if not 8 <= len(result[1:]) <= 15:
        raise ValueError(f"Invalid phone number: {value!r}")
    return result


def normalize_url(value: str) -> str:
    parts = urlsplit(value.strip())
    if parts.scheme not in {"http", "https"} or not parts.netloc:
        raise ValueError(f"Invalid URL: {value!r}")
    host = (parts.hostname or "").encode("idna").decode("ascii").lower()
    netloc = host + (f":{parts.port}" if parts.port else "")
    return urlunsplit((parts.scheme.lower(), netloc, parts.path.rstrip("/") or "/", parts.query, ""))


def derive_usernames(email: str) -> list[tuple[str, float]]:
    local = normalize_email(email).split("@", 1)[0]
    candidates = [(local, 0.55)]
    compact = re.sub(r"[._-]", "", local)
    if compact != local and compact:
        candidates.append((compact, 0.4))
    return candidates


def safe_slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode().lower()
    return re.sub(r"[^a-z0-9]+", "-", value).strip("-")[:64] or "case"


def validate_image_path(value: str) -> Path:
    path = Path(value).expanduser().resolve()
    if not path.is_file():
        raise ValueError(f"Image does not exist: {value}")
    return path

