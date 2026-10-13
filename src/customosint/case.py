"""Case directory lifecycle."""

from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from .database import CaseDatabase
from .normalization import safe_slug


@dataclass(slots=True)
class Case:
    id: str
    name: str
    path: Path
    db: CaseDatabase

    @classmethod
    def create(cls, root: Path, name: str, seeds: list[dict[str, str]]) -> Case:
        stamp = datetime.now().strftime("%Y-%m-%d_%H%M%S")
        case_id = f"{stamp}_{safe_slug(name)}"; path = root / case_id
        for child in ("raw", "normalized", "images", "graph", "report"): (path / child).mkdir(parents=True, exist_ok=True)
        (path / "seeds.json").write_text(json.dumps(seeds, ensure_ascii=False, indent=2), encoding="utf-8")
        (path / "case.json").write_text(json.dumps({"id": case_id, "name": name}, ensure_ascii=False, indent=2), encoding="utf-8")
        db = CaseDatabase(path / "case.db"); db.add_case(case_id, name, {"seeds": seeds})
        return cls(case_id, name, path, db)

    @classmethod
    def open(cls, path: Path) -> Case:
        meta = json.loads((path / "case.json").read_text(encoding="utf-8"))
        return cls(meta["id"], meta["name"], path, CaseDatabase(path / "case.db"))

