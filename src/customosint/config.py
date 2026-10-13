"""Configuration loading with conservative defaults."""

from __future__ import annotations

from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

import yaml


@dataclass(slots=True)
class Settings:
    cases_dir: Path = Path("cases")
    default_depth: int = 2
    minimum_pivot_confidence: float = 0.4
    max_entities: int = 500
    max_provider_runs: int = 200
    timeout: float = 900.0
    provider_timeout: float = 120.0
    concurrency: int = 3
    cache_ttl: int = 3600
    retries: int = 2
    retry_base_delay: float = 1.0
    per_provider_delay: float = 0.5
    providers: dict[str, dict[str, Any]] = field(default_factory=dict)


def load_settings(path: Path | None = None) -> Settings:
    source = path or Path("config.yaml")
    if not source.exists():
        return Settings()
    data = yaml.safe_load(source.read_text(encoding="utf-8")) or {}
    general = data.get("general", {})
    return Settings(
        cases_dir=Path(general.get("cases_dir", "cases")),
        default_depth=int(general.get("default_depth", 2)),
        minimum_pivot_confidence=float(general.get("minimum_pivot_confidence", 0.4)),
        max_entities=int(general.get("max_entities", 500)),
        max_provider_runs=int(general.get("max_provider_runs", 200)),
        timeout=float(general.get("timeout", 900)),
        provider_timeout=float(general.get("provider_timeout", 120)),
        concurrency=int(general.get("concurrency", 3)),
        cache_ttl=int(general.get("cache_ttl", 3600)),
        retries=int(general.get("retries", 2)),
        retry_base_delay=float(general.get("retry_base_delay", 1.0)),
        per_provider_delay=float(general.get("per_provider_delay", 0.5)),
        providers=data.get("providers", {}),
    )
