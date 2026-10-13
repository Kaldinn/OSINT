"""Domain models kept independent from providers and persistence."""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from enum import Enum
from typing import Any
from uuid import uuid4


def utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


class EntityType(str, Enum):
    PERSON = "Person"
    FULL_NAME = "FullName"
    USERNAME = "Username"
    EMAIL = "Email"
    PHONE = "Phone"
    SOCIAL_PROFILE = "SocialProfile"
    URL = "URL"
    DOMAIN = "Domain"
    ORGANIZATION = "Organization"
    LOCATION = "Location"
    IMAGE = "Image"
    IMAGE_HASH = "ImageHash"
    BREACH = "Breach"
    IP_ADDRESS = "IPAddress"
    GITHUB_ACCOUNT = "GitHubAccount"
    GOOGLE_ACCOUNT = "GoogleAccount"
    WEBSITE = "Website"
    EXTERNAL_IDENTIFIER = "ExternalIdentifier"


@dataclass(slots=True)
class Entity:
    type: EntityType
    value: str
    normalized_value: str
    sources: list[str] = field(default_factory=list)
    confidence: float = 0.5
    metadata: dict[str, Any] = field(default_factory=dict)
    depth: int = 0
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["type"] = self.type.value
        return result


@dataclass(slots=True)
class Evidence:
    kind: str
    description: str
    weight: float
    provider: str
    metadata: dict[str, Any] = field(default_factory=dict)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class Relationship:
    source: str
    target: str
    relation: str
    confidence: float
    evidence: list[Evidence] = field(default_factory=list)
    providers: list[str] = field(default_factory=list)
    id: str = field(default_factory=lambda: str(uuid4()))
    created_at: str = field(default_factory=utc_now)

    def to_dict(self) -> dict[str, Any]:
        result = asdict(self)
        result["evidence"] = [item.to_dict() for item in self.evidence]
        return result


@dataclass(slots=True)
class ProviderResult:
    entities: list[Entity] = field(default_factory=list)
    relationships: list[Relationship] = field(default_factory=list)
    raw: Any = None
    status: str = "SUCCESS"
    error: str | None = None
