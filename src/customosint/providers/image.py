"""Local image hashing and ExifTool metadata provider."""

from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

from ..models import Entity, EntityType, Evidence, ProviderResult, Relationship
from .base import Provider


class ImageProvider(Provider):
    name = "image"; supported_entities = {"Image"}
    async def run(self, entity: Entity, raw_dir: Path, timeout: float) -> ProviderResult:
        path = Path(entity.value); raw_dir.mkdir(parents=True, exist_ok=True)
        data = path.read_bytes()
        metadata: dict[str, Any] = {"sha256": hashlib.sha256(data).hexdigest(), "md5": hashlib.md5(data).hexdigest()}
        try:
            import imagehash
            from PIL import Image
            with Image.open(path) as image:
                metadata.update({"width": image.width, "height": image.height, "format": image.format, "phash": str(imagehash.phash(image)), "dhash": str(imagehash.dhash(image))})
        except (ImportError, OSError) as exc: metadata["image_error"] = str(exc)
        exiftool = __import__("shutil").which("exiftool")
        if exiftool:
            code, stdout, stderr = await self.execute([exiftool, "-json", str(path)], timeout)
            if code == 0:
                try: metadata["exif"] = json.loads(stdout)[0]
                except (json.JSONDecodeError, IndexError): metadata["exif_error"] = "malformed ExifTool JSON"
            else: metadata["exif_error"] = stderr.decode(errors="replace")
        (raw_dir / "metadata.json").write_text(json.dumps(metadata, ensure_ascii=False, indent=2), encoding="utf-8")
        return self.normalize(metadata, entity)
    def normalize(self, raw: Any, entity: Entity) -> ProviderResult:
        entity.metadata.update(raw if isinstance(raw, dict) else {}); entity.sources.append(self.name); entity.confidence = 1.0
        hashes = [Entity(EntityType.IMAGE_HASH, str(raw[key]), str(raw[key]), [self.name], 1.0, {"algorithm": key}, entity.depth + 1) for key in ("sha256", "md5", "phash", "dhash") if isinstance(raw, dict) and raw.get(key)]
        relationships = [
            Relationship(
                entity.id,
                item.id,
                "HAS_IMAGE_HASH",
                1.0,
                [Evidence("cryptographic_hash" if item.metadata["algorithm"] == "sha256" else "image_hash", f"Computed {item.metadata['algorithm']} for local image", 1.0, self.name)],
                [self.name],
            )
            for item in hashes
        ]
        return ProviderResult([entity, *hashes], relationships, raw)
