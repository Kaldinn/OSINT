import json

import pytest

from customosint.models import Entity, EntityType
from customosint.providers.base import Provider
from customosint.providers.email import HIBPProvider
from customosint.providers.public import (
    GitHubProvider,
    GravatarProvider,
    SpiderFootProvider,
    _spiderfoot_scan_id,
    _spiderfoot_status,
)


def test_github_normalization():
    seed = Entity(EntityType.USERNAME, "octocat", "octocat")
    result = GitHubProvider().normalize({"login": "octocat", "html_url": "https://github.com/octocat", "location": "Internet"}, seed)
    assert result.entities[0].type == EntityType.GITHUB_ACCOUNT
    assert result.relationships[0].confidence == .72


def test_gravatar_normalization():
    seed = Entity(EntityType.EMAIL, "a@example.com", "a@example.com")
    result = GravatarProvider().normalize({"profile_url": "https://gravatar.com/a", "display_name": "A"}, seed)
    assert result.entities[0].type == EntityType.SOCIAL_PROFILE
    assert result.relationships[0].relation == "HAS_PROFILE"


def test_spiderfoot_normalization_is_low_confidence():
    seed = Entity(EntityType.EMAIL, "a@example.com", "a@example.com")
    result = SpiderFootProvider().normalize([{"type": "INTERNET_NAME", "data": "example.com"}], seed)
    assert result.entities[0].confidence == .45


def test_spiderfoot_lifecycle_parsing():
    assert _spiderfoot_scan_id(["SUCCESS", "scan-1"]) == "scan-1"
    assert _spiderfoot_scan_id({"scan_id": "scan-2"}) == "scan-2"
    assert _spiderfoot_status([["scan-1", "name", "target", None, None, None, "FINISHED"]], "scan-1") == "FINISHED"


def test_malformed_json_is_rejected(tmp_path):
    malformed = tmp_path / "bad.json"
    malformed.write_text("{broken", encoding="utf-8")
    with pytest.raises(json.JSONDecodeError):
        Provider.load_json(malformed)


def test_missing_api_key_is_nonfatal(monkeypatch):
    monkeypatch.delenv("HIBP_API_KEY", raising=False)
    available, reason = HIBPProvider().available()
    assert not available
    assert "API key missing" in reason
