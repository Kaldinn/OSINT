import asyncio
from pathlib import Path

from customosint.case import Case
from customosint.config import Settings
from customosint.engine import InvestigationEngine
from customosint.models import Entity, EntityType, ProviderResult
from customosint.providers.base import Provider


class FakeProvider(Provider):
    name = "fake"; supported_entities = {"Username"}
    def available(self): return True, "ready"
    async def run(self, entity, raw_dir, timeout):
        return ProviderResult([Entity(EntityType.USERNAME, entity.value + "x", entity.normalized_value + "x", ["fake"], .8, depth=entity.depth + 1)], raw={})
    def normalize(self, raw, entity): return ProviderResult()


class MissingProvider(FakeProvider):
    name = "missing"
    def available(self): return False, "program missing"


class TimeoutProvider(FakeProvider):
    name = "timeout"
    async def run(self, entity, raw_dir, timeout):
        await asyncio.sleep(.1); return ProviderResult()


def test_pivot_depth_and_max_entities(tmp_path: Path):
    case = Case.create(tmp_path, "depth", [])
    engine = InvestigationEngine(case, Settings(max_entities=3, provider_timeout=1), [FakeProvider()])
    engine.add_seed("nickname", "abc"); asyncio.run(engine.run(depth=1))
    assert len(case.db.entities()) == 2
    case.db.close()


def test_missing_and_timeout_are_recorded(tmp_path: Path):
    case = Case.create(tmp_path, "fail", [])
    engine = InvestigationEngine(case, Settings(provider_timeout=.01), [MissingProvider(), TimeoutProvider()])
    engine.add_seed("nickname", "abc"); asyncio.run(engine.run(depth=0))
    statuses = {r["provider"]: r["status"] for r in case.db.provider_runs()}
    assert statuses == {"missing": "SKIPPED", "timeout": "TIMEOUT"}
    case.db.close()

