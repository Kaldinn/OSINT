"""Public/API enrichment providers with conservative failure behavior."""

from __future__ import annotations

import asyncio
import hashlib
import json
import os
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import quote, urlencode
from urllib.request import Request, urlopen

from ..models import Entity, EntityType, Evidence, ProviderResult, Relationship
from ..normalization import normalize_url
from .base import Provider


async def _request_json(url: str, headers: dict[str, str], timeout: float, data: bytes | None = None) -> tuple[int, Any]:
    request = Request(url, headers=headers, data=data)
    try:
        response = await asyncio.to_thread(lambda: urlopen(request, timeout=timeout))
        return int(response.status), json.loads(response.read())
    except HTTPError as exc:
        if exc.code == 404:
            return 404, None
        raise ConnectionError(f"HTTP {exc.code} from {url}") from exc
    except (URLError, TimeoutError) as exc:
        raise ConnectionError(str(exc)) from exc


class GitHubProvider(Provider):
    name = "github"; supported_entities = {"Username"}

    async def run(self, entity: Entity, raw_dir: Path, timeout: float) -> ProviderResult:
        headers = {"Accept": "application/vnd.github+json", "User-Agent": "CustomOSINT/0.1", "X-GitHub-Api-Version": "2022-11-28"}
        token = os.getenv("GITHUB_TOKEN")
        if token: headers["Authorization"] = f"Bearer {token}"
        status, raw = await _request_json(f"https://api.github.com/users/{quote(entity.value)}", headers, timeout)
        raw_dir.mkdir(parents=True, exist_ok=True); (raw_dir / "result.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        return ProviderResult(status="SUCCESS", raw=raw) if status == 404 else self.normalize(raw, entity)

    def normalize(self, raw: Any, entity: Entity) -> ProviderResult:
        if not isinstance(raw, dict) or not raw.get("html_url"): return ProviderResult(raw=raw)
        account = Entity(EntityType.GITHUB_ACCOUNT, str(raw["login"]), str(raw["login"]).casefold(), [self.name], .72, {k: raw.get(k) for k in ("html_url", "name", "company", "blog", "location", "bio", "avatar_url") if raw.get(k)}, entity.depth + 1)
        ev = Evidence("provider_match", "GitHub public API returned this login", .72, self.name)
        relation = Relationship(entity.id, account.id, "POSSIBLY_USES", .72, [ev], [self.name])
        return ProviderResult([account], [relation], raw)


class GravatarProvider(Provider):
    name = "gravatar"; supported_entities = {"Email"}
    def available(self) -> tuple[bool, str]:
        return (True, "ready") if os.getenv("GRAVATAR_API_KEY") else (False, "API key missing: GRAVATAR_API_KEY")

    async def run(self, entity: Entity, raw_dir: Path, timeout: float) -> ProviderResult:
        digest = hashlib.sha256(entity.normalized_value.encode()).hexdigest()
        key = os.getenv("GRAVATAR_API_KEY")
        if not key: return ProviderResult(status="SKIPPED", error="API key missing")
        status, raw = await _request_json(f"https://api.gravatar.com/v3/profiles/{digest}", {"Authorization": f"Bearer {key}", "User-Agent": "CustomOSINT/0.1"}, timeout)
        raw_dir.mkdir(parents=True, exist_ok=True); (raw_dir / "result.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        return ProviderResult(raw=raw) if status == 404 else self.normalize(raw, entity)

    def normalize(self, raw: Any, entity: Entity) -> ProviderResult:
        if not isinstance(raw, dict) or not raw.get("profile_url"): return ProviderResult(raw=raw)
        profile = Entity(EntityType.SOCIAL_PROFILE, str(raw["profile_url"]), normalize_url(str(raw["profile_url"])), [self.name], .9, {k: raw.get(k) for k in ("display_name", "location", "company", "description", "avatar_url") if raw.get(k)}, entity.depth + 1)
        ev = Evidence("exact_email", "Gravatar profile resolved from the exact normalized email hash", .9, self.name)
        relation = Relationship(entity.id, profile.id, "HAS_PROFILE", .9, [ev], [self.name])
        return ProviderResult([profile], [relation], raw)


class KeybaseProvider(Provider):
    name = "keybase"; supported_entities = {"Username"}
    async def run(self, entity: Entity, raw_dir: Path, timeout: float) -> ProviderResult:
        status, raw = await _request_json(f"https://keybase.io/_/api/1.0/user/lookup.json?username={quote(entity.value)}", {"User-Agent": "CustomOSINT/0.1"}, timeout)
        raw_dir.mkdir(parents=True, exist_ok=True); (raw_dir / "result.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        return ProviderResult(raw=raw) if status == 404 else self.normalize(raw, entity)
    def normalize(self, raw: Any, entity: Entity) -> ProviderResult:
        them = raw.get("them") if isinstance(raw, dict) else None
        if not isinstance(them, list) or not them: return ProviderResult(raw=raw)
        username = str(them[0].get("basics", {}).get("username", entity.value))
        url = f"https://keybase.io/{username}"
        profile = Entity(EntityType.SOCIAL_PROFILE, url, normalize_url(url), [self.name], .68, {"platform": "Keybase", "username": username}, entity.depth + 1)
        ev = Evidence("provider_match", "Keybase public lookup returned this username", .68, self.name)
        return ProviderResult([profile], [Relationship(entity.id, profile.id, "POSSIBLY_USES", .68, [ev], [self.name])], raw)


class GHuntProvider(Provider):
    name = "ghunt"; command = "ghunt"; supported_entities = {"Email"}
    async def run(self, entity: Entity, raw_dir: Path, timeout: float) -> ProviderResult:
        raw_dir.mkdir(parents=True, exist_ok=True); output = raw_dir / "result.json"
        code, stdout, stderr = await self.execute(["ghunt", "email", entity.value, "--json", str(output)], timeout)
        (raw_dir / "stdout.txt").write_bytes(stdout); (raw_dir / "stderr.txt").write_bytes(stderr)
        if code != 0: return ProviderResult(status="ERROR", error="GHunt CLI/version did not accept structured export")
        try: return self.normalize(json.loads(output.read_text(encoding="utf-8")), entity)
        except (OSError, json.JSONDecodeError) as exc: return ProviderResult(status="ERROR", error=f"Malformed GHunt JSON: {exc}")
    def normalize(self, raw: Any, entity: Entity) -> ProviderResult:
        gaia = raw.get("gaia_id") or raw.get("gaiaId") if isinstance(raw, dict) else None
        if not gaia: return ProviderResult(raw=raw)
        account = Entity(EntityType.GOOGLE_ACCOUNT, str(gaia), str(gaia), [self.name], .8, raw, entity.depth + 1)
        ev = Evidence("exact_email", "GHunt resolved a Google identifier from the email", .8, self.name)
        return ProviderResult([account], [Relationship(entity.id, account.id, "HAS_PROFILE", .8, [ev], [self.name])], raw)


class SpiderFootProvider(Provider):
    name = "spiderfoot"; supported_entities = {"Email", "Username", "Domain", "IPAddress"}
    def available(self) -> tuple[bool, str]:
        return (True, "ready") if os.getenv("SPIDERFOOT_URL") else (False, "SPIDERFOOT_URL missing; start the local SpiderFoot server")
    async def run(self, entity: Entity, raw_dir: Path, timeout: float) -> ProviderResult:
        base = os.environ["SPIDERFOOT_URL"].rstrip("/")
        payload = urlencode({"scanname": f"customosint-{entity.id[:8]}", "scantarget": entity.value, "modulelist": "all"}).encode()
        _, raw = await _request_json(f"{base}/startscan", {"User-Agent": "CustomOSINT/0.1", "Content-Type": "application/x-www-form-urlencoded"}, timeout, payload)
        raw_dir.mkdir(parents=True, exist_ok=True); (raw_dir / "start.json").write_text(json.dumps(raw, ensure_ascii=False, indent=2), encoding="utf-8")
        return ProviderResult(raw=raw, status="STARTED", error="Scan started; export it from SpiderFoot after completion")
    def normalize(self, raw: Any, entity: Entity) -> ProviderResult:
        entities: list[Entity] = []
        for row in raw if isinstance(raw, list) else []:
            value, kind = row.get("data"), str(row.get("type", ""))
            mapping = {"EMAILADDR": EntityType.EMAIL, "INTERNET_NAME": EntityType.DOMAIN, "IP_ADDRESS": EntityType.IP_ADDRESS, "SOCIAL_MEDIA": EntityType.SOCIAL_PROFILE}
            if value and kind in mapping: entities.append(Entity(mapping[kind], str(value), str(value).casefold(), [self.name], .45, {"spiderfoot_type": kind}, entity.depth + 1))
        return ProviderResult(entities=entities, raw=raw)
