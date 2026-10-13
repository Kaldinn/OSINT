"""Controlled breadth-first enrichment pipeline."""

from __future__ import annotations

import asyncio
import json
from collections import deque
from collections.abc import Iterable
from pathlib import Path

from .case import Case
from .config import Settings
from .correlation import correlate_images, correlate_profiles
from .models import Entity, EntityType, Evidence, ProviderResult, Relationship
from .normalization import derive_usernames, normalize_email, normalize_phone, normalize_username
from .providers import Provider, built_in_providers
from .providers.image import ImageProvider


class InvestigationEngine:
    def __init__(self, case: Case, settings: Settings, providers: Iterable[Provider] | None = None, fixture: Path | None = None, no_cache: bool = False):
        self.case = case; self.settings = settings; self.providers = list(providers or [*built_in_providers(), ImageProvider()]); self.fixture = fixture
        self.queue: deque[Entity] = deque(); self.provider_runs = 0; self.no_cache = no_cache
        self._provider_locks = {provider.name: asyncio.Lock() for provider in self.providers}

    def add_seed(self, kind: str, value: str) -> Entity:
        type_map = {"email": EntityType.EMAIL, "nickname": EntityType.USERNAME, "phone": EntityType.PHONE, "name": EntityType.FULL_NAME, "image": EntityType.IMAGE}
        if kind == "email":
            normalized = normalize_email(value)
        elif kind == "nickname":
            normalized = normalize_username(value)
        elif kind == "phone":
            normalized = normalize_phone(value)
        elif kind == "name":
            normalized = " ".join(value.casefold().split())
        elif kind == "image":
            normalized = str(Path(value).resolve())
        else:
            raise ValueError(f"Unsupported seed type: {kind}")
        entity = Entity(type_map[kind], value, normalized, ["seed"], 1.0, depth=0)
        entity, created = self.case.db.upsert_entity(entity)
        if created: self.queue.append(entity)
        if kind == "email":
            for username, confidence in derive_usernames(value):
                derived = Entity(EntityType.USERNAME, username, normalize_username(username), ["derived"], confidence, {"hypothesis": True}, 1)
                derived, is_new = self.case.db.upsert_entity(derived)
                ev = Evidence("derived", "Username candidate derived from email local-part", confidence, "core")
                self.case.db.upsert_relationship(Relationship(entity.id, derived.id, "DERIVED_FROM", confidence, [ev], ["core"]))
                if is_new and confidence >= self.settings.minimum_pivot_confidence: self.queue.append(derived)
        return entity

    async def run(self, depth: int, selected: set[str] | None = None, aggressive: bool = False) -> None:
        semaphore = asyncio.Semaphore(self.settings.concurrency)
        while self.queue and len(self.case.db.entities()) < self.settings.max_entities and self.provider_runs < self.settings.max_provider_runs:
            current = self.queue.popleft()
            if current.depth > 0 and current.depth >= depth: continue
            candidates = [
                provider
                for provider in self.providers
                if current.type.value in provider.supported_entities
                and (not selected or provider.name in selected)
                and (
                    (selected is not None and provider.name in selected)
                    or self.settings.providers.get(provider.name, {}).get("enabled", True)
                )
            ]
            remaining_runs = self.settings.max_provider_runs - self.provider_runs
            candidates = candidates[: max(0, remaining_runs)]
            async def invoke(provider: Provider, subject: Entity = current) -> None:
                async with semaphore: await self._invoke(provider, subject, depth, aggressive)
            await asyncio.gather(*(invoke(provider) for provider in candidates))
        correlate_profiles(self.case.db)
        correlate_images(self.case.db)
        self._write_normalized()

    async def _invoke(self, provider: Provider, entity: Entity, max_depth: int, aggressive: bool) -> None:
        self.provider_runs += 1; run_id = self.case.db.start_provider_run(provider.name, entity.normalized_value)
        if self.fixture is None:
            available, reason = provider.available()
            if not available:
                self.case.db.finish_provider_run(run_id, "SKIPPED", error=reason); return
        raw_dir = self.case.path / "raw" / provider.name / f"{self.provider_runs:04d}"
        try:
            if self.fixture:
                result = self._fixture_result(provider, entity)
            else:
                cached = None if self.no_cache else self.case.db.get_cache(provider.name, entity.normalized_value, self.settings.cache_ttl)
                if cached is not None:
                    result = provider.normalize(cached, entity); result.status = "CACHED"
                else:
                    async with self._provider_locks[provider.name]:
                        result = await self._run_with_retry(provider, entity, raw_dir)
                        await asyncio.sleep(self.settings.per_provider_delay)
                    if result.status == "SUCCESS" and result.raw is not None:
                        self.case.db.set_cache(provider.name, entity.normalized_value, result.raw)
        except TimeoutError:
            self.case.db.finish_provider_run(run_id, "TIMEOUT", error="provider timeout"); return
        except Exception as exc:
            self.case.db.finish_provider_run(run_id, "ERROR", error=f"{type(exc).__name__}: {exc}"); return
        raw_dir.mkdir(parents=True, exist_ok=True)
        raw_file = raw_dir / "normalized-input.json"
        raw_file.write_text(json.dumps(result.raw, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        self.case.db.add_raw_result(run_id, raw_file)
        self.case.db.finish_provider_run(run_id, result.status, str(raw_file.relative_to(self.case.path)), result.error)
        id_map: dict[str, str] = {}
        for found in result.entities:
            if len(self.case.db.entities()) >= self.settings.max_entities:
                break
            old_id = found.id; stored, created = self.case.db.upsert_entity(found); id_map[old_id] = stored.id
            if stored.type == EntityType.IMAGE:
                self.case.db.upsert_image(stored)
            threshold = 0.0 if aggressive else self.settings.minimum_pivot_confidence
            if created and stored.depth <= max_depth and stored.confidence >= threshold and len(self.case.db.entities()) < self.settings.max_entities: self.queue.append(stored)
        for relation in result.relationships:
            relation.source = id_map.get(relation.source, relation.source); relation.target = id_map.get(relation.target, relation.target)
            self.case.db.upsert_relationship(relation)

    async def _run_with_retry(self, provider: Provider, entity: Entity, raw_dir: Path) -> ProviderResult:
        last_error: Exception | None = None
        for attempt in range(self.settings.retries + 1):
            try:
                return await asyncio.wait_for(
                    provider.run(entity, raw_dir, self.settings.provider_timeout),
                    timeout=self.settings.provider_timeout,
                )
            except TimeoutError:
                raise
            except (OSError, ConnectionError) as exc:
                last_error = exc
                if attempt < self.settings.retries:
                    await asyncio.sleep(self.settings.retry_base_delay * (2**attempt))
        assert last_error is not None
        raise last_error

    def _fixture_result(self, provider: Provider, entity: Entity) -> ProviderResult:
        candidates = [self.fixture / provider.name / f"{entity.normalized_value}.json", self.fixture / f"{provider.name}.json"]  # type: ignore[operator]
        for path in candidates:
            if path.exists(): return provider.normalize(json.loads(path.read_text(encoding="utf-8")), entity)
        return ProviderResult(status="SKIPPED", error="fixture missing")

    def _write_normalized(self) -> None:
        normalized = self.case.path / "normalized"
        for name, rows in (
            ("entities.jsonl", self.case.db.entities()),
            ("relationships.jsonl", self.case.db.relationships()),
            ("evidence.jsonl", self.case.db.evidence()),
        ):
            (normalized / name).write_text("\n".join(json.dumps(row.to_dict(), ensure_ascii=False) for row in rows) + "\n", encoding="utf-8")
