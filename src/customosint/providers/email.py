"""Email-oriented providers."""

from __future__ import annotations

import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError
from urllib.request import Request, urlopen

from ..models import Entity, EntityType, Evidence, ProviderResult, Relationship
from .base import Provider


class HoleheProvider(Provider):
    name = "holehe"; command = "holehe"; supported_entities = {"Email"}

    async def run(self, entity: Entity, raw_dir: Path, timeout: float) -> ProviderResult:
        raw_dir.mkdir(parents=True, exist_ok=True)
        code, stdout, stderr = await self.execute(["holehe", entity.value, "--only-used", "--no-color"], timeout)
        (raw_dir / "stdout.txt").write_bytes(stdout); (raw_dir / "stderr.txt").write_bytes(stderr)
        if code != 0: return ProviderResult(status="ERROR", error=stderr.decode(errors="replace"))
        return self.normalize(stdout.decode(errors="replace"), entity)

    def normalize(self, raw: Any, entity: Entity) -> ProviderResult:
        entities: list[Entity] = []; relations: list[Relationship] = []
        for line in str(raw).splitlines():
            clean = line.strip().lstrip("[+]").strip()
            if not clean or clean.startswith(("Email used", "Rate limit")): continue
            service = clean.split()[0].strip(":")
            account = Entity(EntityType.EXTERNAL_IDENTIFIER, f"{service}:{entity.value}", f"{service.lower()}:{entity.normalized_value}", [self.name], 0.6, {"service": service}, entity.depth + 1)
            ev = Evidence("provider_match", f"Holehe indicated registration at {service}", 0.6, self.name)
            relations.append(Relationship(entity.id, account.id, "POSSIBLY_USES", 0.6, [ev], [self.name])); entities.append(account)
        return ProviderResult(entities, relations, raw)


class HIBPProvider(Provider):
    name = "hibp"; supported_entities = {"Email"}
    def available(self) -> tuple[bool, str]:
        return (True, "ready") if os.getenv("HIBP_API_KEY") else (False, "API key missing: HIBP_API_KEY")
    async def run(self, entity: Entity, raw_dir: Path, timeout: float) -> ProviderResult:
        key = os.getenv("HIBP_API_KEY")
        if not key: return ProviderResult(status="SKIPPED", error="API key missing")
        request = Request(f"https://haveibeenpwned.com/api/v3/breachedaccount/{entity.value}?truncateResponse=false", headers={"hibp-api-key": key, "user-agent": "CustomOSINT/0.1"})
        try:
            data = await __import__("asyncio").to_thread(lambda: urlopen(request, timeout=timeout).read())
        except HTTPError as exc:
            if exc.code == 404: data = b"[]"
            else: return ProviderResult(status="ERROR", error=f"HIBP HTTP {exc.code}")
        raw_dir.mkdir(parents=True, exist_ok=True); (raw_dir / "result.json").write_bytes(data)
        try: return self.normalize(json.loads(data), entity)
        except json.JSONDecodeError as exc: return ProviderResult(status="ERROR", error=f"Malformed HIBP response: {exc}")
    def normalize(self, raw: Any, entity: Entity) -> ProviderResult:
        entities: list[Entity] = []; relations: list[Relationship] = []
        for row in raw if isinstance(raw, list) else []:
            name = str(row.get("Name", "unknown")); breach = Entity(EntityType.BREACH, name, name.casefold(), [self.name], 0.9, {"breach_date": row.get("BreachDate"), "data_classes": row.get("DataClasses", [])}, entity.depth + 1)
            ev = Evidence("exact_email", f"HIBP reports the address in {name}", 0.9, self.name)
            relations.append(Relationship(entity.id, breach.id, "APPEARED_IN_BREACH", 0.9, [ev], [self.name])); entities.append(breach)
        return ProviderResult(entities, relations, raw)

