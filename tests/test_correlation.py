from pathlib import Path

from customosint.correlation import correlate_images, correlate_profiles
from customosint.database import CaseDatabase
from customosint.models import Entity, EntityType


def test_common_username_is_weak(tmp_path: Path):
    db = CaseDatabase(tmp_path / "case.db")
    db.upsert_entity(Entity(EntityType.SOCIAL_PROFILE, "https://a.test/john", "https://a.test/john", ["a"], metadata={"username": "john"}))
    db.upsert_entity(Entity(EntityType.SOCIAL_PROFILE, "https://b.test/john", "https://b.test/john", ["b"], metadata={"username": "john"}))
    assert correlate_profiles(db) == 1
    assert db.relationships()[0].confidence == .2
    db.close()


def test_multiple_independent_signals_and_conflict(tmp_path: Path):
    db = CaseDatabase(tmp_path / "case.db")
    first = {"username": "unusual_handle_938", "blog": "https://same.test", "location": "Warsaw"}
    second = {"username": "unusual_handle_938", "blog": "https://same.test", "location": "Toronto"}
    db.upsert_entity(Entity(EntityType.SOCIAL_PROFILE, "https://a.test/u", "https://a.test/u", ["a"], metadata=first))
    db.upsert_entity(Entity(EntityType.GITHUB_ACCOUNT, "unusual_handle_938", "unusual_handle_938", ["github"], metadata=second))
    correlate_profiles(db)
    relation = db.relationships()[0]
    assert .6 < relation.confidence < .8
    assert any(item.kind == "conflicting_location" for item in relation.evidence)
    db.close()


def test_perceptual_image_match(tmp_path: Path):
    db = CaseDatabase(tmp_path / "case.db")
    db.upsert_entity(Entity(EntityType.IMAGE, "a.png", "a.png", ["image"], metadata={"phash": "0000000000000000"}))
    db.upsert_entity(Entity(EntityType.IMAGE, "b.png", "b.png", ["image"], metadata={"phash": "0000000000000001"}))
    assert correlate_images(db) == 1
    assert db.relationships()[0].relation == "POSSIBLE_SAME_IMAGE"
    db.close()
