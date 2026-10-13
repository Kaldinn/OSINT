"""Username provider adapters using documented machine-readable outputs."""

from __future__ import annotations

import csv
import json
from pathlib import Path
from typing import Any

from ..models import Entity, EntityType, Evidence, ProviderResult, Relationship
from ..normalization import normalize_url
from .base import Provider


def _profile(entity: Entity, provider: str, site: str, url: str) -> tuple[Entity, Relationship]:
    normalized = normalize_url(url)
    profile = Entity(EntityType.SOCIAL_PROFILE, url, normalized, [provider], 0.62, {"platform": site, "username": entity.value}, entity.depth + 1)
    evidence = Evidence("provider_match", f"{provider} reported a public profile on {site}", 0.62, provider)
    relation = Relationship(entity.id, profile.id, "POSSIBLY_USES", 0.62, [evidence], [provider])
    return profile, relation


class MaigretProvider(Provider):
    name = "maigret"; command = "maigret"; supported_entities = {"Username"}

    async def run(self, entity: Entity, raw_dir: Path, timeout: float) -> ProviderResult:
        target = raw_dir / "result.ndjson"; raw_dir.mkdir(parents=True, exist_ok=True)
        code, stdout, stderr = await self.execute(["maigret", entity.value, "--json", "ndjson", "--no-recursion", "--folderoutput", str(raw_dir)], timeout)
        (raw_dir / "stdout.txt").write_bytes(stdout); (raw_dir / "stderr.txt").write_bytes(stderr)
        candidates = list(raw_dir.glob("*.json")) + list(raw_dir.glob("*.ndjson"))
        if not candidates:
            target.write_bytes(stdout)
        else: target = candidates[0]
        if code != 0: return ProviderResult(raw=stdout.decode(errors="replace"), status="ERROR", error=stderr.decode(errors="replace"))
        try:
            rows = [json.loads(line) for line in target.read_text(encoding="utf-8").splitlines() if line.strip()]
            return self.normalize(rows, entity)
        except (OSError, json.JSONDecodeError) as exc: return ProviderResult(status="ERROR", error=f"Malformed Maigret output: {exc}")

    def normalize(self, raw: Any, entity: Entity) -> ProviderResult:
        entities: list[Entity] = []; relations: list[Relationship] = []
        rows = raw if isinstance(raw, list) else [raw]
        for row in rows:
            sites = row.get("sites", row) if isinstance(row, dict) else {}
            if not isinstance(sites, dict): continue
            for site, data in sites.items():
                if not isinstance(data, dict): continue
                status = str(data.get("status", data.get("status_code", ""))).lower()
                url = data.get("url_user") or data.get("url")
                if url and ("claimed" in status or status in {"true", "found", "200"}):
                    try: profile, relation = _profile(entity, self.name, str(site), str(url))
                    except ValueError: continue
                    entities.append(profile); relations.append(relation)
        return ProviderResult(entities, relations, raw)


class SherlockProvider(Provider):
    name = "sherlock"; command = "sherlock"; supported_entities = {"Username"}

    async def run(self, entity: Entity, raw_dir: Path, timeout: float) -> ProviderResult:
        raw_dir.mkdir(parents=True, exist_ok=True); output = raw_dir / "result.csv"
        code, stdout, stderr = await self.execute(["sherlock", entity.value, "--csv", "--output", str(output), "--no-color"], timeout)
        (raw_dir / "stdout.txt").write_bytes(stdout); (raw_dir / "stderr.txt").write_bytes(stderr)
        if code != 0: return ProviderResult(status="ERROR", error=stderr.decode(errors="replace"))
        try:
            with output.open(encoding="utf-8-sig", newline="") as handle: rows = list(csv.DictReader(handle))
            return self.normalize(rows, entity)
        except (OSError, csv.Error) as exc: return ProviderResult(status="ERROR", error=f"Malformed Sherlock output: {exc}")

    def normalize(self, raw: Any, entity: Entity) -> ProviderResult:
        entities: list[Entity] = []; relations: list[Relationship] = []
        for row in raw if isinstance(raw, list) else []:
            url = row.get("url_main") or row.get("url") or row.get("URL")
            status = str(row.get("status", row.get("Status", "claimed"))).lower()
            if url and status not in {"not found", "unclaimed", "false"}:
                try: profile, relation = _profile(entity, self.name, str(row.get("name") or row.get("site_name") or "unknown"), str(url))
                except ValueError: continue
                entities.append(profile); relations.append(relation)
        return ProviderResult(entities, relations, raw)

