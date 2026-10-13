from pathlib import Path
from xml.etree import ElementTree

from customosint.exporters import export_all
from customosint.models import Entity, EntityType, Relationship


def test_graph_exports(tmp_path: Path):
    a = Entity(EntityType.USERNAME, "alice", "alice")
    b = Entity(EntityType.URL, "https://example.com/", "https://example.com/")
    export_all(tmp_path, [a, b], [Relationship(a.id, b.id, "LINKS_TO", .7)])
    ElementTree.parse(tmp_path / "case.gexf"); ElementTree.parse(tmp_path / "case.graphml")
    for name in ("neo4j.cypher", "maltego_import.csv", "index.html"): assert (tmp_path / name).stat().st_size > 0

