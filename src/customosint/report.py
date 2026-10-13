"""Self-contained HTML investigation report."""

from __future__ import annotations

import html
from pathlib import Path

from .case import Case
from .models import EntityType
from .scoring import confidence_label


def generate_report(case: Case) -> Path:
    entities, relations, runs = case.db.entities(), case.db.relationships(), case.db.provider_runs()
    counts = {kind: sum(e.type == kind for e in entities) for kind in EntityType}
    rows = "".join(f"<tr><td>{html.escape(e.type.value)}</td><td>{html.escape(e.value)}</td><td>{e.confidence:.2f}</td><td>{html.escape(', '.join(e.sources))}</td><td>{e.depth}</td></tr>" for e in entities)
    rel_rows = "".join(f"<tr><td>{html.escape(r.relation)}</td><td>{r.confidence:.2f}</td><td>{confidence_label(r.confidence)}</td><td>{html.escape(', '.join(r.providers))}</td></tr>" for r in relations)
    errors = "".join(f"<li><b>{html.escape(str(r['provider']))}</b>: {html.escape(str(r['status']))} — {html.escape(str(r['error'] or ''))}</li>" for r in runs if r["status"] != "SUCCESS") or "<li>None</li>"
    strong = sum(r.confidence >= .8 for r in relations); probable = sum(.6 <= r.confidence < .8 for r in relations)
    document = f"""<!doctype html><html lang="en"><head><meta charset="utf-8"><title>{html.escape(case.name)} — CustomOSINT</title><style>:root{{color-scheme:dark}}body{{font:15px system-ui;max-width:1200px;margin:auto;padding:2rem;background:#08111d;color:#dce7f7}}h1,h2{{color:#75d5ff}}.cards{{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px}}.card{{padding:16px;background:#122238;border:1px solid #29425f;border-radius:10px}}table{{width:100%;border-collapse:collapse}}th,td{{padding:9px;border-bottom:1px solid #29425f;text-align:left}}a{{color:#75d5ff}}</style></head><body><h1>{html.escape(case.name)}</h1><p>Evidence-first report. A possible match is not asserted as identity.</p><h2>Executive Summary</h2><div class=cards><div class=card>Entities<br><b>{len(entities)}</b></div><div class=card>Relationships<br><b>{len(relations)}</b></div><div class=card>Social profiles<br><b>{counts[EntityType.SOCIAL_PROFILE]}</b></div><div class=card>Images<br><b>{counts[EntityType.IMAGE]}</b></div><div class=card>Breaches<br><b>{counts[EntityType.BREACH]}</b></div><div class=card>Strong / probable<br><b>{strong} / {probable}</b></div></div><p><a href="../graph/index.html">Interactive graph</a></p><h2>Seeds, profiles, emails, phones, images and findings</h2><table><thead><tr><th>Type</th><th>Value</th><th>Confidence</th><th>Sources</th><th>Depth</th></tr></thead><tbody>{rows}</tbody></table><h2>Relationships</h2><table><thead><tr><th>Relation</th><th>Confidence</th><th>Class</th><th>Providers</th></tr></thead><tbody>{rel_rows}</tbody></table><h2>Provider errors and skips</h2><ul>{errors}</ul><h2>Legal and analytical notice</h2><p>Use only on data you are authorized to investigate. Findings require human verification. No plaintext passwords are collected or stored.</p></body></html>"""
    output = case.path / "report" / "index.html"; output.write_text(document, encoding="utf-8"); return output

