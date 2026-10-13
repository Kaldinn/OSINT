"""SQLite persistence and canonical deduplication."""

from __future__ import annotations

import hashlib
import json
import sqlite3
import time
from pathlib import Path
from typing import Any

from .models import Entity, EntityType, Evidence, Relationship, utc_now

SCHEMA = """
PRAGMA foreign_keys=ON;
CREATE TABLE IF NOT EXISTS cases(id TEXT PRIMARY KEY, name TEXT NOT NULL, created_at TEXT NOT NULL, metadata TEXT NOT NULL);
CREATE TABLE IF NOT EXISTS entities(id TEXT PRIMARY KEY, type TEXT NOT NULL, value TEXT NOT NULL, normalized_value TEXT NOT NULL,
 sources TEXT NOT NULL, confidence REAL NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL, depth INTEGER NOT NULL,
 UNIQUE(type, normalized_value));
CREATE TABLE IF NOT EXISTS relationships(id TEXT PRIMARY KEY, source TEXT NOT NULL, target TEXT NOT NULL, relation TEXT NOT NULL,
 confidence REAL NOT NULL, providers TEXT NOT NULL, created_at TEXT NOT NULL, UNIQUE(source,target,relation));
CREATE TABLE IF NOT EXISTS evidence(id TEXT PRIMARY KEY, relationship_id TEXT NOT NULL, kind TEXT NOT NULL, description TEXT NOT NULL,
 weight REAL NOT NULL, provider TEXT NOT NULL, metadata TEXT NOT NULL, created_at TEXT NOT NULL,
 FOREIGN KEY(relationship_id) REFERENCES relationships(id));
CREATE TABLE IF NOT EXISTS provider_runs(id INTEGER PRIMARY KEY AUTOINCREMENT, provider TEXT NOT NULL, input TEXT NOT NULL,
 started_at TEXT NOT NULL, finished_at TEXT, status TEXT NOT NULL, return_code INTEGER, raw_output_file TEXT, error TEXT);
CREATE TABLE IF NOT EXISTS raw_results(id INTEGER PRIMARY KEY AUTOINCREMENT, provider_run_id INTEGER NOT NULL, path TEXT NOT NULL,
 sha256 TEXT NOT NULL, created_at TEXT NOT NULL, FOREIGN KEY(provider_run_id) REFERENCES provider_runs(id));
CREATE TABLE IF NOT EXISTS images(id TEXT PRIMARY KEY, entity_id TEXT NOT NULL, path TEXT NOT NULL, sha256 TEXT NOT NULL,
 md5 TEXT NOT NULL, phash TEXT, dhash TEXT, metadata TEXT NOT NULL, FOREIGN KEY(entity_id) REFERENCES entities(id));
CREATE TABLE IF NOT EXISTS cache(provider TEXT NOT NULL, input_key TEXT NOT NULL, result_json TEXT NOT NULL,
 created_at REAL NOT NULL, PRIMARY KEY(provider,input_key));
"""


class CaseDatabase:
    def __init__(self, path: Path):
        self.path = path
        self.connection = sqlite3.connect(path)
        self.connection.row_factory = sqlite3.Row
        self.connection.executescript(SCHEMA)

    def close(self) -> None:
        self.connection.close()

    def add_case(self, case_id: str, name: str, metadata: dict[str, Any] | None = None) -> None:
        self.connection.execute("INSERT OR IGNORE INTO cases VALUES(?,?,?,?)", (case_id, name, utc_now(), json.dumps(metadata or {})))
        self.connection.commit()

    def upsert_entity(self, entity: Entity) -> tuple[Entity, bool]:
        row = self.connection.execute("SELECT * FROM entities WHERE type=? AND normalized_value=?", (entity.type.value, entity.normalized_value)).fetchone()
        if row:
            sources = sorted(set(json.loads(row["sources"])) | set(entity.sources))
            confidence = max(float(row["confidence"]), entity.confidence)
            metadata = {**json.loads(row["metadata"]), **entity.metadata}
            self.connection.execute("UPDATE entities SET sources=?,confidence=?,metadata=?,depth=MIN(depth,?) WHERE id=?", (json.dumps(sources), confidence, json.dumps(metadata), entity.depth, row["id"]))
            self.connection.commit()
            entity.id = str(row["id"]); entity.sources = sources; entity.confidence = confidence; entity.metadata = metadata
            return entity, False
        self.connection.execute("INSERT INTO entities VALUES(?,?,?,?,?,?,?,?,?)", (entity.id, entity.type.value, entity.value, entity.normalized_value, json.dumps(entity.sources), entity.confidence, json.dumps(entity.metadata), entity.created_at, entity.depth))
        self.connection.commit()
        return entity, True

    def upsert_relationship(self, relation: Relationship) -> tuple[Relationship, bool]:
        row = self.connection.execute("SELECT id,confidence,providers FROM relationships WHERE source=? AND target=? AND relation=?", (relation.source, relation.target, relation.relation)).fetchone()
        if row:
            relation.id = str(row["id"])
            relation.confidence = max(float(row["confidence"]), relation.confidence)
            relation.providers = sorted(set(json.loads(row["providers"])) | set(relation.providers))
            self.connection.execute("UPDATE relationships SET confidence=?,providers=? WHERE id=?", (relation.confidence, json.dumps(relation.providers), relation.id))
            created = False
        else:
            self.connection.execute("INSERT INTO relationships VALUES(?,?,?,?,?,?,?)", (relation.id, relation.source, relation.target, relation.relation, relation.confidence, json.dumps(relation.providers), relation.created_at))
            created = True
        for evidence in relation.evidence:
            self.connection.execute("INSERT OR IGNORE INTO evidence VALUES(?,?,?,?,?,?,?,?)", (evidence.id, relation.id, evidence.kind, evidence.description, evidence.weight, evidence.provider, json.dumps(evidence.metadata), evidence.created_at))
        self.connection.commit()
        return relation, created

    def start_provider_run(self, provider: str, input_value: str) -> int:
        cur = self.connection.execute("INSERT INTO provider_runs(provider,input,started_at,status) VALUES(?,?,?,?)", (provider, input_value, utc_now(), "RUNNING"))
        self.connection.commit()
        if cur.lastrowid is None:
            raise RuntimeError("SQLite did not return a provider run id")
        return int(cur.lastrowid)

    def finish_provider_run(self, run_id: int, status: str, raw_path: str | None = None, error: str | None = None, return_code: int | None = None) -> None:
        self.connection.execute("UPDATE provider_runs SET finished_at=?,status=?,raw_output_file=?,error=?,return_code=? WHERE id=?", (utc_now(), status, raw_path, error, return_code, run_id)); self.connection.commit()

    def add_raw_result(self, run_id: int, path: Path) -> None:
        digest = hashlib.sha256(path.read_bytes()).hexdigest()
        self.connection.execute(
            "INSERT INTO raw_results(provider_run_id,path,sha256,created_at) VALUES(?,?,?,?)",
            (run_id, str(path), digest, utc_now()),
        )
        self.connection.commit()

    def upsert_image(self, entity: Entity) -> None:
        metadata = entity.metadata
        if not metadata.get("sha256") or not metadata.get("md5"):
            return
        self.connection.execute(
            "INSERT OR REPLACE INTO images VALUES(?,?,?,?,?,?,?,?)",
            (
                entity.id,
                entity.id,
                entity.value,
                metadata["sha256"],
                metadata["md5"],
                metadata.get("phash"),
                metadata.get("dhash"),
                json.dumps(metadata, ensure_ascii=False, default=str),
            ),
        )
        self.connection.commit()

    def entities(self) -> list[Entity]:
        rows = self.connection.execute("SELECT * FROM entities ORDER BY depth,type,normalized_value").fetchall()
        return [Entity(id=r["id"], type=EntityType(r["type"]), value=r["value"], normalized_value=r["normalized_value"], sources=json.loads(r["sources"]), confidence=r["confidence"], metadata=json.loads(r["metadata"]), created_at=r["created_at"], depth=r["depth"]) for r in rows]

    def relationships(self) -> list[Relationship]:
        result: list[Relationship] = []
        for r in self.connection.execute("SELECT * FROM relationships ORDER BY confidence DESC"):
            evidence_rows = self.connection.execute(
                "SELECT * FROM evidence WHERE relationship_id=? ORDER BY created_at",
                (r["id"],),
            ).fetchall()
            evidence = [
                Evidence(
                    id=item["id"],
                    kind=item["kind"],
                    description=item["description"],
                    weight=item["weight"],
                    provider=item["provider"],
                    metadata=json.loads(item["metadata"]),
                    created_at=item["created_at"],
                )
                for item in evidence_rows
            ]
            result.append(Relationship(id=r["id"], source=r["source"], target=r["target"], relation=r["relation"], confidence=r["confidence"], evidence=evidence, providers=json.loads(r["providers"]), created_at=r["created_at"]))
        return result

    def evidence(self) -> list[Evidence]:
        return [
            Evidence(
                id=row["id"],
                kind=row["kind"],
                description=row["description"],
                weight=row["weight"],
                provider=row["provider"],
                metadata={**json.loads(row["metadata"]), "relationship_id": row["relationship_id"]},
                created_at=row["created_at"],
            )
            for row in self.connection.execute("SELECT * FROM evidence ORDER BY created_at")
        ]

    def provider_runs(self) -> list[dict[str, Any]]:
        return [dict(row) for row in self.connection.execute("SELECT * FROM provider_runs ORDER BY id")]

    def get_cache(self, provider: str, input_key: str, ttl: int) -> Any | None:
        row = self.connection.execute(
            "SELECT result_json,created_at FROM cache WHERE provider=? AND input_key=?",
            (provider, input_key),
        ).fetchone()
        if not row or time.time() - float(row["created_at"]) > ttl:
            return None
        return json.loads(str(row["result_json"]))

    def set_cache(self, provider: str, input_key: str, raw: Any) -> None:
        self.connection.execute(
            "INSERT OR REPLACE INTO cache VALUES(?,?,?,?)",
            (provider, input_key, json.dumps(raw, ensure_ascii=False, default=str), time.time()),
        )
        self.connection.commit()
