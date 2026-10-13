from pathlib import Path

import pytest

from customosint.case import Case
from customosint.database import CaseDatabase
from customosint.models import Entity, EntityType, Evidence, Relationship
from customosint.normalization import (
    derive_usernames,
    normalize_email,
    normalize_phone,
    normalize_username,
)
from customosint.scoring import combine_evidence


def test_normalization():
    assert normalize_email(" User@EXAMPLE.COM ") == "user@example.com"
    assert normalize_phone("123 456 789") == "+48123456789"
    assert normalize_phone("+48 123 456 789") == "+48123456789"
    assert normalize_username(" @Janek93 ") == "janek93"
    assert derive_usernames("john.smith93@example.com") == [("john.smith93", .55), ("johnsmith93", .4)]


@pytest.mark.parametrize("value", ["no-at", "x@y", "@example.com"])
def test_invalid_email(value):
    with pytest.raises(ValueError): normalize_email(value)


def test_entity_and_relation_deduplication(tmp_path: Path):
    db = CaseDatabase(tmp_path / "case.db")
    a, created = db.upsert_entity(Entity(EntityType.USERNAME, "Alice", "alice"))
    b, created_again = db.upsert_entity(Entity(EntityType.USERNAME, "alice", "alice", ["x"], .8))
    assert created and not created_again and a.id == b.id and len(db.entities()) == 1
    target, _ = db.upsert_entity(Entity(EntityType.URL, "https://x.test/", "https://x.test/"))
    r = Relationship(a.id, target.id, "LINKS_TO", .5)
    db.upsert_relationship(r); db.upsert_relationship(Relationship(a.id, target.id, "LINKS_TO", .7))
    assert len(db.relationships()) == 1 and db.relationships()[0].confidence == .7


def test_scoring_diminishing_returns_and_independence():
    one = Evidence("same_name", "name", .25, "a")
    duplicate = Evidence("same_city", "city", .2, "a")
    independent = Evidence("same_avatar", "avatar", .7, "b")
    assert combine_evidence([one, duplicate]) == .25
    assert .77 < combine_evidence([one, independent]) < .8
    assert combine_evidence([one, independent], conflicts=.5) < .4


def test_case_layout(tmp_path: Path):
    case = Case.create(tmp_path, "Example Case", [{"type": "email", "value": "a@b.pl"}])
    assert (case.path / "raw").is_dir() and (case.path / "case.db").exists()
    case.db.close()


def test_cache_ttl(tmp_path: Path):
    db = CaseDatabase(tmp_path / "case.db")
    db.set_cache("provider", "input", {"ok": True})
    assert db.get_cache("provider", "input", 60) == {"ok": True}
    assert db.get_cache("provider", "input", -1) is None
    db.close()


def test_relationship_evidence_round_trip(tmp_path: Path):
    db = CaseDatabase(tmp_path / "case.db")
    source, _ = db.upsert_entity(Entity(EntityType.USERNAME, "alice", "alice"))
    target, _ = db.upsert_entity(Entity(EntityType.URL, "https://x.test", "https://x.test/"))
    evidence = Evidence("direct_profile_link", "direct link", .9, "fixture")
    db.upsert_relationship(Relationship(source.id, target.id, "LINKS_TO", .9, [evidence], ["fixture"]))
    assert db.relationships()[0].evidence[0].description == "direct link"
    assert db.evidence()[0].metadata["relationship_id"] == db.relationships()[0].id
    db.close()
