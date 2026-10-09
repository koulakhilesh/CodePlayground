import argparse
from html import escape
import json
from pathlib import Path
from urllib.parse import urlparse

from collect_wren import write_json
from wren_records import Record, Tables

THEMES = {
    "interiors_and_domes": "Interiors and domes",
    "fire_and_rebuilding": "Fire, war and rebuilding",
    "lost_churches": "Lost churches",
    "people_and_stories": "People and stories",
    "travelling_stone": "Travelling stone",
}
EVIDENCE_KINDS = {"direct_statement", "descriptive_comparison"}


def related_ids(claim: Record) -> set[str]:
    value = claim.get("value")
    return set(value.get("related_church_ids", [])) if isinstance(value, dict) else set()


def validate_connection(edge: Record, churches: dict[str, Record], claims: dict[str, Record]) -> list[Record]:
    identifier = edge.get("connection_id", "?")
    for field in ("connection_id", "relation", "explanation", "caveat"):
        if not str(edge.get(field) or "").strip():
            raise ValueError(f"{identifier}: missing {field}")
    if edge.get("theme") not in THEMES:
        raise ValueError(f"{identifier}: unknown theme {edge.get('theme')}")
    if edge.get("evidence_kind") not in EVIDENCE_KINDS:
        raise ValueError(f"{identifier}: unknown evidence kind")
    endpoints = {edge.get("from_id"), edge.get("to_id")}
    if len(endpoints) != 2 or not endpoints <= set(churches):
        raise ValueError(f"{identifier}: endpoints must be two known churches")
    if not edge.get("claim_ids"):
        raise ValueError(f"{identifier}: connection requires evidence")
    evidence = []
    for claim_id in edge["claim_ids"]:
        claim = claims.get(claim_id)
        if claim is None:
            raise ValueError(f"{identifier}: missing evidence {claim_id}")
        if claim.get("review_status") != "verified":
            raise ValueError(f"{identifier}: evidence {claim_id} is not verified")
        if claim["subject_id"] not in endpoints:
            raise ValueError(f"{identifier}: evidence {claim_id} belongs to neither endpoint")
        evidence.append(claim)
    if edge["evidence_kind"] == "direct_statement":
        if not any((endpoints - {claim["subject_id"]}) <= related_ids(claim) for claim in evidence):
            raise ValueError(f"{identifier}: direct statement must name the other endpoint")
    elif {claim["subject_id"] for claim in evidence} != endpoints:
        raise ValueError(f"{identifier}: descriptive comparison requires evidence for both endpoints")
    return evidence


def build_graph(tables: Tables, connections: list[Record]) -> Record:
    churches = {row["church_id"]: row for row in tables["churches"]}
    claims = {row["claim_id"]: row for row in tables["claims"]}
    sources = {row["source_id"]: row for row in tables.get("sources", [])}
    church_by_place = {row["place_id"]: row["church_id"] for row in tables.get("places", [])}
    closures: dict[str, list[Record]] = {}
    for visit in tables.get("visits", []):
        church_id = church_by_place.get(visit.get("place_id"))
        if church_id and visit.get("closure"):
            closures.setdefault(church_id, []).append(dict(visit["closure"]))
    seen = set()
    edges = []
    for edge in sorted(connections, key=lambda row: str(row.get("connection_id"))):
        if edge.get("connection_id") in seen:
            raise ValueError(f"Duplicate connection {edge.get('connection_id')}")
        seen.add(edge.get("connection_id"))
        evidence = validate_connection(edge, churches, claims)
        edges.append({key: edge[key] for key in ("connection_id", "from_id", "to_id", "relation", "theme",
                                                 "evidence_kind", "explanation", "caveat")}
                     | {"claim_ids": list(edge["claim_ids"]),
                        "sources": [{"claim_id": claim["claim_id"], "url": sources.get(claim["source_id"], {}).get("url"),
                                     "locator": claim.get("locator")} for claim in evidence]})
    connected = sorted({identifier for edge in edges for identifier in (edge["from_id"], edge["to_id"])})
    nodes = [{"church_id": identifier, "name": churches[identifier]["name"], "cohort": churches[identifier]["cohort"],
              "wren_work": churches[identifier].get("wren_work"), "closure_notices": closures.get(identifier, [])}
             for identifier in connected]
    used = {edge["theme"] for edge in edges}
    claim_url = {identifier: sources.get(claim["source_id"], {}).get("url") for identifier, claim in claims.items()}
    parishes = {row["parish_id"]: row for row in tables.get("parishes", [])}
    unions: dict[str, Record] = {}
    moves = []
    for event in sorted(tables.get("events", []), key=lambda row: row["event_id"]):
        church = churches.get(event["church_id"])
        if not church:
            continue
        tier = ("verified" if all(claims.get(c, {}).get("review_status") == "verified" for c in event.get("claim_ids", []))
                else event.get("evidence_tier", "reported"))
        urls = sorted({claim_url[c] for c in event.get("claim_ids", []) if claim_url.get(c)})
        if event["kind"] == "parish_merger" and event.get("parish_id") in parishes:
            entry = unions.setdefault(event["church_id"], {"church_id": event["church_id"], "name": church["name"],
                                                           "theme": "lost_churches", "parishes": [], "source_urls": set()})
            entry["parishes"].append({"name": parishes[event["parish_id"]]["name"], "evidence_tier": tier})
            entry["source_urls"].update(urls)
        elif event["kind"] == "relocation" and event.get("destination"):
            moves.append({"church_id": event["church_id"], "name": church["name"], "theme": "travelling_stone",
                          "component": event.get("phase"), "destination": event["destination"],
                          "earliest_year": event.get("earliest_year"), "latest_year": event.get("latest_year"),
                          "evidence_tier": tier, "source_urls": urls, "caveat": event.get("caveat", "")})
    parish_unions = [entry | {"source_urls": sorted(entry["source_urls"]),
                              "parishes": sorted(entry["parishes"], key=lambda row: row["name"])}
                     for entry in sorted(unions.values(), key=lambda row: row["name"])]
    used |= {"lost_churches"} if parish_unions else set()
    used |= {"travelling_stone"} if moves else set()
    return {"nodes": nodes, "edges": edges, "parish_unions": parish_unions, "relocations": moves,
            "coverage": {"connected_candidates": len(connected), "candidates": len(churches),
                         "unconnected_candidate_ids": sorted(set(churches) - set(connected)),
                         "empty_themes": sorted(set(THEMES) - used),
                         "edges_by_theme": {theme: sum(edge["theme"] == theme for edge in edges) for theme in THEMES},
                         "churches_with_parish_unions": len(parish_unions),
                         "parish_unions": sum(len(entry["parishes"]) for entry in parish_unions),
                         "relocations": len(moves)},
            "limitations": ["Connections are documented relationships, not walking directions or influence claims.",
                            "Unconnected candidates lack reviewed relationship evidence; absence is not evidence of no relationship.",
                            "Parish unions and relocations carry their own evidence tier; 'reported' means a single secondary list."]}


def write_graph(graph: Record, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [output_dir / "discovery.json", output_dir / "discovery_graph.html"]
    write_json(paths[0], graph)
    names = {node["church_id"]: node["name"] for node in graph["nodes"]}
    options = '<option value="all">All themes</option>' + "".join(
        f'<option value="{key}">{escape(label)}</option>' for key, label in THEMES.items())
    items = []
    for edge in graph["edges"]:
        links = " ".join(f'<a href="{escape(source["url"], quote=True)}">Source ({escape(str(source["locator"]))})</a>'
                         for source in edge["sources"]
                         if source["url"] and urlparse(source["url"]).scheme in {"http", "https"})
        items.append(f'<li data-theme="{edge["theme"]}"><h2>{escape(names[edge["from_id"]])} &harr; '
                     f'{escape(names[edge["to_id"]])}</h2><p class="kind">{escape(THEMES[edge["theme"]])} &middot; '
                     f'{escape(edge["relation"].replace("_", " "))} &middot; {escape(edge["evidence_kind"].replace("_", " "))}</p>'
                     f'<p>{escape(edge["explanation"])}</p><p class="caveat">{escape(edge["caveat"])}</p><p>{links}</p></li>')
    def source_links(urls: list[str]) -> str:
        return " ".join(f'<a href="{escape(url, quote=True)}">Source</a>' for url in urls if urlparse(url).scheme in {"http", "https"})
    for entry in graph.get("parish_unions", []):
        names_list = ", ".join(f'{escape(row["name"])} ({escape(row["evidence_tier"])})' for row in entry["parishes"])
        items.append(f'<li data-theme="lost_churches"><h2>{escape(entry["name"])} &larr; lost parishes</h2>'
                     f'<p class="kind">{escape(THEMES["lost_churches"])} &middot; parish union</p>'
                     f'<p>Churches burned in 1666 and not rebuilt, whose parishes were united with this one: {names_list}.</p>'
                     f'<p class="caveat">Union date not given by the list; reported tier is a single secondary source.</p>'
                     f'<p>{source_links(entry["source_urls"])}</p></li>')
    for move in graph.get("relocations", []):
        years = ("not stated" if move["earliest_year"] is None and move["latest_year"] is None
                 else f'{move["earliest_year"]}' if move["earliest_year"] == move["latest_year"]
                 else f'{move["earliest_year"] or "?"}-{move["latest_year"] or "?"}')
        items.append(f'<li data-theme="travelling_stone"><h2>{escape(move["name"])} &rarr; {escape(move["destination"])}</h2>'
                     f'<p class="kind">{escape(THEMES["travelling_stone"])} &middot; {escape(str(move["component"]).replace("_", " "))} &middot; {escape(move["evidence_tier"])}</p>'
                     f'<p>Reported year: {escape(years)}.</p><p class="caveat">{escape(move["caveat"] or "Destination and year as reported; not a visiting recommendation.")}</p>'
                     f'<p>{source_links(move["source_urls"])}</p></li>')
    empty = ", ".join(THEMES[theme] for theme in graph["coverage"]["empty_themes"]) or "none"
    coverage = graph["coverage"]
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Wren discovery connections</title><style>
body {{ margin: 0; background: #fafafa; color: #262626; font-family: Georgia, serif; }}
main {{ max-width: 860px; margin: auto; padding: 20px; }} h1 {{ font-size: 28px; }} h2 {{ font-size: 19px; overflow-wrap: anywhere; }}
li {{ list-style: none; border-bottom: 1px solid #ccc; padding: 6px 0 14px; }} ul {{ padding: 0; }}
p {{ line-height: 1.5; }} .kind {{ color: #00756a; }} .caveat {{ font-style: italic; }} a {{ color: #00756a; overflow-wrap: anywhere; }}
select {{ font: inherit; padding: 4px; max-width: 100%; }}
</style></head><body><main><h1>Wren discovery connections</h1>
<p>Documented relationships between places. These are not walking directions, opening advice or claims of architectural influence.</p>
<p>{coverage["connected_candidates"]} of {coverage["candidates"]} candidates currently have reviewed connections. Themes without evidence: {escape(empty)}.</p>
<label for="theme">Theme </label><select id="theme">{options}</select>
<ul id="edges">{"".join(items)}</ul></main>
<script>
document.getElementById("theme").addEventListener("change", event => {{
  for (const item of document.querySelectorAll("#edges li")) {{
    item.hidden = event.target.value !== "all" && item.dataset.theme !== event.target.value;
  }}
}});
</script></body></html>
'''
    paths[1].write_text(document, encoding="utf-8")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Export evidence-backed Wren discovery connections")
    parser.add_argument("--data", type=Path, default=Path("data/london_wren_churches"))
    parser.add_argument("--review", type=Path, default=Path("london-wren-churches/review"))
    parser.add_argument("--output", type=Path, default=Path("london-wren-churches/exports"))
    args = parser.parse_args()
    tables = json.loads((args.data / "tables_reviewed.json").read_text())
    graph = build_graph(tables, json.loads((args.review / "connections.json").read_text()))
    write_graph(graph, args.output)
    print(json.dumps(graph["coverage"], indent=2))


if __name__ == "__main__":
    main()
