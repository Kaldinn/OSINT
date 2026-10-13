"""Dependency-free graph exports for common analyst tools."""

from __future__ import annotations

import csv
import html
import json
from pathlib import Path

from .models import Entity, Relationship


def export_all(path: Path, entities: list[Entity], relations: list[Relationship]) -> None:
    path.mkdir(parents=True, exist_ok=True); by_id = {e.id: e for e in entities}
    nodes_gexf = "".join(f'<node id="{html.escape(e.id)}" label="{html.escape(e.value)}"><attvalues><attvalue for="0" value="{e.type.value}"/><attvalue for="1" value="{e.confidence}"/></attvalues></node>' for e in entities)
    edges_gexf = "".join(f'<edge id="{i}" source="{r.source}" target="{r.target}" label="{html.escape(r.relation)}" weight="{r.confidence}"/>' for i, r in enumerate(relations))
    (path / "case.gexf").write_text(f'<?xml version="1.0" encoding="UTF-8"?><gexf xmlns="http://www.gexf.net/1.3" version="1.3"><graph mode="static" defaultedgetype="directed"><attributes class="node"><attribute id="0" title="type" type="string"/><attribute id="1" title="confidence" type="float"/></attributes><nodes>{nodes_gexf}</nodes><edges>{edges_gexf}</edges></graph></gexf>', encoding="utf-8")
    nodes_ml = "".join(f'<node id="{e.id}"><data key="label">{html.escape(e.value)}</data><data key="type">{e.type.value}</data></node>' for e in entities)
    edges_ml = "".join(f'<edge source="{r.source}" target="{r.target}"><data key="relation">{r.relation}</data><data key="confidence">{r.confidence}</data></edge>' for r in relations)
    (path / "case.graphml").write_text(f'<?xml version="1.0" encoding="UTF-8"?><graphml xmlns="http://graphml.graphdrawing.org/xmlns"><key id="label" for="node" attr.name="label" attr.type="string"/><key id="type" for="node" attr.name="type" attr.type="string"/><key id="relation" for="edge" attr.name="relation" attr.type="string"/><key id="confidence" for="edge" attr.name="confidence" attr.type="double"/><graph edgedefault="directed">{nodes_ml}{edges_ml}</graph></graphml>', encoding="utf-8")
    def cypher(value: str) -> str: return value.replace("\\", "\\\\").replace("'", "\\'")
    lines = [f"MERGE (n:Entity {{id:'{e.id}'}}) SET n.type='{e.type.value}', n.value='{cypher(e.value)}', n.confidence={e.confidence};" for e in entities]
    lines += [f"MATCH (a:Entity {{id:'{r.source}'}}),(b:Entity {{id:'{r.target}'}}) MERGE (a)-[:RELATED {{kind:'{r.relation}', confidence:{r.confidence}}}]->(b);" for r in relations]
    (path / "neo4j.cypher").write_text("\n".join(lines), encoding="utf-8")
    with (path / "maltego_import.csv").open("w", newline="", encoding="utf-8") as handle:
        writer = csv.writer(handle); writer.writerow(["SourceType", "SourceValue", "Relation", "TargetType", "TargetValue", "Confidence", "Evidence", "Provider"])
        for r in relations:
            a, b = by_id.get(r.source), by_id.get(r.target)
            if a and b: writer.writerow([a.type.value, a.value, r.relation, b.type.value, b.value, r.confidence, "; ".join(e.description for e in r.evidence), ";".join(r.providers)])
    graph_data = {"nodes": [{"id": e.id, "label": e.value, "type": e.type.value, "confidence": e.confidence, "depth": e.depth, "providers": e.sources, "metadata": e.metadata} for e in entities], "edges": [{"from": r.source, "to": r.target, "label": r.relation, "confidence": r.confidence, "providers": r.providers} for r in relations]}
    template = """<!doctype html><html><head><meta charset=utf-8><title>CustomOSINT graph</title><style>body{font:14px system-ui;margin:0;background:#09111f;color:#dce8ff}header{padding:14px;background:#101c30;display:flex;gap:14px;flex-wrap:wrap}svg{width:100vw;height:75vh}.node{cursor:pointer}.edge{stroke:#53657d}#detail{padding:12px;white-space:pre-wrap}select,input{background:#14263d;color:#fff}</style></head><body><header><label>Minimum confidence <input id=min type=range min=0 max=1 step=.05 value=0> <span id=mv>0</span></label><label>Entity type <select id=type><option value=''>all</option></select></label><label>Provider <select id=provider><option value=''>all</option></select></label><label>Maximum depth <input id=depth type=number min=0 value=99></label></header><svg id=g></svg><div id=detail>Click a node</div><script>const D=__DATA__,s=document.getElementById('g'),min=document.getElementById('min'),type=document.getElementById('type'),provider=document.getElementById('provider'),depth=document.getElementById('depth');[...new Set(D.nodes.map(x=>x.type))].sort().forEach(x=>type.add(new Option(x,x)));[...new Set(D.nodes.flatMap(x=>x.providers))].sort().forEach(x=>provider.add(new Option(x,x)));function draw(){let m=+min.value,t=type.value,p=provider.value,d=+depth.value;mv.textContent=m;s.innerHTML='';let n=D.nodes.filter(x=>x.confidence>=m&&x.depth<=d&&(!t||x.type===t)&&(!p||x.providers.includes(p))),ids=new Set(n.map(x=>x.id)),w=s.clientWidth,h=s.clientHeight;n.forEach((x,i)=>{x.x=w/2+Math.cos(i*6.28/Math.max(n.length,1))*Math.min(w,h)*.34;x.y=h/2+Math.sin(i*6.28/Math.max(n.length,1))*Math.min(w,h)*.34});let map=Object.fromEntries(n.map(x=>[x.id,x]));D.edges.filter(e=>ids.has(e.from)&&ids.has(e.to)&&e.confidence>=m).forEach(e=>{let l=document.createElementNS('http://www.w3.org/2000/svg','line');Object.entries({x1:map[e.from].x,y1:map[e.from].y,x2:map[e.to].x,y2:map[e.to].y,class:'edge'}).forEach(([k,v])=>l.setAttribute(k,v));s.append(l)});n.forEach(x=>{let c=document.createElementNS('http://www.w3.org/2000/svg','circle');Object.entries({cx:x.x,cy:x.y,r:8+(x.confidence*8),fill:'#58c7ff',class:'node'}).forEach(([k,v])=>c.setAttribute(k,v));c.onclick=()=>detail.textContent=JSON.stringify(x,null,2);s.append(c)})}for(let e of [min,type,provider,depth])e.oninput=draw;draw()</script></body></html>"""
    (path / "index.html").write_text(template.replace("__DATA__", json.dumps(graph_data, ensure_ascii=False).replace("</", "<\\/")), encoding="utf-8")
