"""Cross-provider correlation with explicit evidence and conflict penalties."""

from __future__ import annotations

from itertools import combinations

from .database import CaseDatabase
from .models import Entity, EntityType, Evidence, Relationship
from .scoring import combine_evidence

COMMON_USERNAMES = {
    "admin", "administrator", "alex", "anna", "demo", "guest", "john", "maria",
    "root", "support", "test", "user", "webmaster",
}


def _username(entity: Entity) -> str | None:
    value = entity.metadata.get("username")
    if value:
        return str(value).casefold().lstrip("@")
    if entity.type in {EntityType.USERNAME, EntityType.GITHUB_ACCOUNT}:
        return entity.normalized_value.casefold()
    return None


def correlate_profiles(database: CaseDatabase) -> int:
    """Create cautious profile-to-profile hypotheses from independent signals."""
    profiles = [
        entity
        for entity in database.entities()
        if entity.type in {EntityType.SOCIAL_PROFILE, EntityType.GITHUB_ACCOUNT, EntityType.GOOGLE_ACCOUNT}
    ]
    created = 0
    for left, right in combinations(profiles, 2):
        if set(left.sources) == set(right.sources):
            continue
        evidence: list[Evidence] = []
        conflicts = 0.0
        left_username, right_username = _username(left), _username(right)
        if left_username and left_username == right_username:
            common = left_username in COMMON_USERNAMES or len(left_username) < 5
            weight = 0.2 if common else 0.58
            evidence.append(Evidence("common_username" if common else "rare_username", "Matching username across independent providers", weight, "correlation"))
        for key, kind, weight in (("blog", "same_website", .82), ("avatar_url", "same_avatar", .7)):
            if left.metadata.get(key) and left.metadata.get(key) == right.metadata.get(key):
                evidence.append(Evidence(kind, f"Matching {key}", weight, "correlation"))
        if left.metadata.get("name") and left.metadata.get("name") == right.metadata.get("name"):
            evidence.append(Evidence("same_full_name", "Matching display name", .25, "correlation"))
        left_location, right_location = left.metadata.get("location"), right.metadata.get("location")
        if left_location and right_location:
            if str(left_location).casefold() == str(right_location).casefold():
                evidence.append(Evidence("same_city", "Matching location", .2, "correlation"))
            else:
                conflicts += .25
                evidence.append(Evidence("conflicting_location", "Conflicting profile locations", 0.0, "correlation", {"left": left_location, "right": right_location}))
        positive = [item for item in evidence if item.weight > 0]
        if not positive:
            continue
        confidence = combine_evidence(positive, conflicts)
        source, target = sorted((left.id, right.id))
        _, is_new = database.upsert_relationship(Relationship(source, target, "POSSIBLY_SAME_PERSON", confidence, evidence, sorted(set(left.sources + right.sources))))
        created += int(is_new)
    return created


def correlate_images(database: CaseDatabase, maximum_distance: int = 8) -> int:
    """Relate local images with close 64-bit perceptual hashes."""
    images = [entity for entity in database.entities() if entity.type == EntityType.IMAGE and entity.metadata.get("phash")]
    created = 0
    for left, right in combinations(images, 2):
        try:
            distance = (int(str(left.metadata["phash"]), 16) ^ int(str(right.metadata["phash"]), 16)).bit_count()
        except ValueError:
            continue
        if distance > maximum_distance:
            continue
        confidence = round(.9 - (distance / 40), 4)
        evidence = Evidence("same_avatar", f"Perceptual hash distance is {distance}", confidence, "image-correlation", {"distance": distance})
        source, target = sorted((left.id, right.id))
        _, is_new = database.upsert_relationship(Relationship(source, target, "POSSIBLE_SAME_IMAGE", confidence, [evidence], ["image-correlation"]))
        created += int(is_new)
    return created
