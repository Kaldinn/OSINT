"""Self-contained, evidence-oriented HTML investigation report."""

from __future__ import annotations

import html
from pathlib import Path

from .case import Case
from .models import Entity, EntityType
from .scoring import confidence_label


def _entity_table(title: str, entities: list[Entity]) -> str:
    rows = "".join(
        "<tr>"
        f"<td>{html.escape(entity.type.value)}</td><td>{html.escape(entity.value)}</td>"
        f"<td>{entity.confidence:.2f}</td><td>{html.escape(', '.join(entity.sources))}</td>"
        f"<td>{entity.depth}</td></tr>"
        for entity in entities
    ) or '<tr><td colspan="5">No findings</td></tr>'
    return (
        f"<h2>{html.escape(title)}</h2><table><thead><tr><th>Type</th><th>Value</th>"
        f"<th>Confidence</th><th>Sources</th><th>Depth</th></tr></thead><tbody>{rows}</tbody></table>"
    )


def generate_report(case: Case) -> Path:
    entities, relations, runs = case.db.entities(), case.db.relationships(), case.db.provider_runs()
    counts = {kind: sum(entity.type == kind for entity in entities) for kind in EntityType}
    sections = [
        _entity_table("Seeds", [entity for entity in entities if "seed" in entity.sources]),
        _entity_table("Profiles", [entity for entity in entities if entity.type in {EntityType.SOCIAL_PROFILE, EntityType.GITHUB_ACCOUNT, EntityType.GOOGLE_ACCOUNT}]),
        _entity_table("Emails", [entity for entity in entities if entity.type == EntityType.EMAIL]),
        _entity_table("Phone numbers", [entity for entity in entities if entity.type == EntityType.PHONE]),
        _entity_table("Breach exposure (no passwords)", [entity for entity in entities if entity.type == EntityType.BREACH]),
        _entity_table("Images and metadata", [entity for entity in entities if entity.type in {EntityType.IMAGE, EntityType.IMAGE_HASH}]),
        _entity_table("Uncertain findings", [entity for entity in entities if entity.confidence < .6]),
    ]
    relation_rows = "".join(
        "<tr>"
        f"<td>{html.escape(relation.relation)}</td><td>{relation.confidence:.2f}</td>"
        f"<td>{confidence_label(relation.confidence)}</td>"
        f"<td>{html.escape('; '.join(item.description for item in relation.evidence))}</td>"
        f"<td>{html.escape(', '.join(relation.providers))}</td></tr>"
        for relation in relations
    ) or '<tr><td colspan="5">No relationships</td></tr>'
    errors = "".join(
        f"<li><b>{html.escape(str(run['provider']))}</b>: {html.escape(str(run['status']))} — "
        f"{html.escape(str(run['error'] or ''))}</li>"
        for run in runs
        if run["status"] not in {"SUCCESS", "CACHED"}
    ) or "<li>None</li>"
    strong = sum(relation.confidence >= .8 for relation in relations)
    probable = sum(.6 <= relation.confidence < .8 for relation in relations)
    possible = sum(.3 <= relation.confidence < .6 for relation in relations)
    summary = (
        f"<div class=cards><div class=card>Input seeds<br><b>{sum('seed' in e.sources for e in entities)}</b></div>"
        f"<div class=card>Unique entities<br><b>{len(entities)}</b></div>"
        f"<div class=card>Social profiles<br><b>{counts[EntityType.SOCIAL_PROFILE] + counts[EntityType.GITHUB_ACCOUNT] + counts[EntityType.GOOGLE_ACCOUNT]}</b></div>"
        f"<div class=card>Images<br><b>{counts[EntityType.IMAGE]}</b></div>"
        f"<div class=card>Breaches<br><b>{counts[EntityType.BREACH]}</b></div>"
        f"<div class=card>Strong / probable / possible<br><b>{strong} / {probable} / {possible}</b></div></div>"
    )
    document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(case.name)} — CustomOSINT</title><style>:root{{color-scheme:dark}}body{{font:15px system-ui;max-width:1200px;margin:auto;padding:2rem;background:#08111d;color:#dce7f7}}h1,h2{{color:#75d5ff}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}.card{{padding:16px;background:#122238;border:1px solid #29425f;border-radius:10px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #29425f;text-align:left}}a{{color:#75d5ff}}</style></head><body><h1>{html.escape(case.name)}</h1><p>Evidence-first report. A possible match is not asserted as identity.</p><h2>Executive Summary</h2>{summary}<p><a href="../graph/index.html">Interactive graph</a></p>{''.join(sections)}<h2>Relationships and evidence</h2><table><thead><tr><th>Relation</th><th>Confidence</th><th>Class</th><th>Evidence</th><th>Providers</th></tr></thead><tbody>{relation_rows}</tbody></table><h2>Provider errors and skips</h2><ul>{errors}</ul><h2>Reverse Image Search</h2><p>Use image paths and hashes as manual pivots in lawful public reverse-image services. Protected interfaces are not automated or bypassed.</p><h2>Legal and analytical notice</h2><p>Use only on data you are authorized to investigate. Findings require human verification. No plaintext passwords are collected or stored.</p></body></html>"""
    output = case.path / "report" / "index.html"
    output.write_text(document, encoding="utf-8")
    return output
