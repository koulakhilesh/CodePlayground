import argparse
from copy import deepcopy
from datetime import date
from html import escape
import json
from pathlib import Path
from typing import Callable
from urllib.parse import urlparse

from collect_wren import write_json
from routing_wren import route_leg
from wren_records import Record, Tables


def validate_walk(walk: Record, tables: Tables) -> list[str]:
    errors = []
    places = {row["place_id"]: row for row in tables.get("places", [])}
    visits = {row["visit_id"]: row for row in tables.get("visits", [])}
    claims = {row["claim_id"]: row for row in tables.get("claims", [])}
    if not walk.get("walk_id") or not walk.get("title") or not walk.get("checked_at"):
        errors.append("Walk requires ID, title and checked_at")
    for field in ("stops", "optional_stops"):
        for stop in walk.get(field, []):
            place = places.get(stop.get("place_id"))
            visit = visits.get(stop.get("visit_id"))
            if not place or not visit or visit["place_id"] != stop.get("place_id"):
                errors.append("Stop requires matching place and visit records")
                continue
            if visit["access_type"] != stop.get("access_type"):
                errors.append("Stop access type must match sourced visit")
            if place.get("role") == "relocated_component":
                errors.append("Relocated component is not a local London walk stop")
            support = set(stop.get("claim_ids", [])) | set(visit.get("claim_ids", []))
            if not support:
                errors.append("Stop requires verified visitor evidence")
            for identifier in support:
                claim = claims.get(identifier)
                if not claim or claim.get("review_status") != "verified":
                    errors.append("Stop requires verified claim evidence")
                elif claim["subject_id"] not in {place["church_id"], place["place_id"]}:
                    errors.append("Stop claim ownership does not match place")
            if visit.get("closure") and field == "stops" and stop.get("access_type") == "interior":
                errors.append("Announced closure cannot be a required interior stop")
            if stop.get("visit_minutes") is not None:
                if type(stop["visit_minutes"]) is not int or stop["visit_minutes"] <= 0 or stop.get("duration_basis") != "editorial_estimate":
                    errors.append("Visit minutes require a positive editorial estimate")
            try:
                date.fromisoformat(visit.get("checked_at", ""))
            except (TypeError, ValueError):
                errors.append("Visit requires valid checked_at date")
    if walk.get("legs"):
        errors.append("Measured pedestrian legs are not supported in this pilot; omit route metrics until a reviewed routing adapter exists")
    for field in ("walking_minutes", "total_minutes", "distance_m", "open_now"):
        if walk.get(field) is not None:
            errors.append(f"Unsupported derived walk field: {field}")
    return errors


def build_walks(tables: Tables, walks: list[Record], router: Callable[[Record, Record], Record] | None = None) -> list[Record]:
    places = {row["place_id"]: row for row in tables["places"]}
    visits = {row["visit_id"]: row for row in tables["visits"]}
    churches = {row["church_id"]: row for row in tables["churches"]}
    claims = {row["claim_id"]: row for row in tables["claims"]}
    sources = {row["source_id"]: row for row in tables["sources"]}
    access = {claim["subject_id"]: claim for claim in tables["claims"]
              if claim.get("field") == "accessibility" and claim["review_status"] == "verified"}
    output = []
    for walk in walks:
        errors = validate_walk(walk, tables)
        if errors:
            raise ValueError("; ".join(errors))
        result = deepcopy(walk)
        result.update(walking_minutes=None, total_minutes=None, distance_m=None,
                      route_status="stop_sequence_only", accessibility_status="not_assessed")
        for field in ("stops", "optional_stops"):
            for stop in result.get(field, []):
                place = places[stop["place_id"]]
                visit = visits[stop["visit_id"]]
                published_access = access.get(place["church_id"])
                stop.update(name=churches[place["church_id"]]["name"],
                            location_role=place["role"], coordinate_status="source_reported_not_entrance_verified",
                            hours=visit.get("hours"), restrictions=visit.get("restrictions"),
                            closure=visit.get("closure"), fee=visit.get("fee"),
                            accessibility=visit.get("accessibility") or (published_access["value"]["quotes"] if published_access else None),
                            checked_at=visit["checked_at"])
                support = set(stop.get("claim_ids", [])) | set(visit["claim_ids"])
                if published_access:
                    support.add(published_access["claim_id"])
                stop["source_urls"] = sorted({sources[claims[identifier]["source_id"]]["url"] for identifier in support})
        if router and len(result["stops"]) > 1:
            stops = [places[stop["place_id"]] for stop in result["stops"]]
            result["legs"] = [router(a, b) for a, b in zip(stops, stops[1:])]
            result["distance_m"] = sum(leg["distance_m"] for leg in result["legs"])
            result["walking_minutes"] = sum(leg["walking_minutes"] for leg in result["legs"])
            visit_minutes = [stop.get("visit_minutes") for stop in result["stops"]]
            if all(isinstance(value, int) for value in visit_minutes):
                result["total_minutes"] = result["walking_minutes"] + sum(visit_minutes)
            result["route_status"] = "routed_between_site_coordinates"
        output.append(result)
    return output


def format_hours(hours: Record | None) -> str:
    if hours is None:
        return "Published hours not established."
    return f"{hours.get('scope', 'Published access')}: {', '.join(hours.get('days', []))}, {hours.get('opens', '?')}-{hours.get('closes', '?')} ({hours.get('timezone', 'time zone unknown')})."


def write_walks(walks: list[Record], output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    paths = [output_dir / "pilot_walks.json", output_dir / "pilot_walk.html"]
    write_json(paths[0], walks)
    sections = []
    for walk in walks:
        groups = []
        for field, title in (("stops", "Suggested stop sequence"), ("optional_stops", "Restricted optional stops")):
            items = []
            for stop in walk.get(field, []):
                links = " ".join(f'<a href="{escape(url, quote=True)}">Official source {index}</a>'
                                 for index, url in enumerate(stop["source_urls"], 1)
                                 if urlparse(url).scheme in {"http", "https"})
                closure = stop.get("closure")
                closure_text = ""
                if closure:
                    closure_text = f"Announced closure from about {closure.get('start_approximate', '?')}, {closure.get('duration_text', '')}. Reopening not confirmed. Do not plan interior access without checking."
                minutes = stop.get("visit_minutes")
                estimate = f"Editorial visit estimate: {minutes} minutes; excludes walking." if minutes else "No visit duration estimated."
                items.append(f'<li><h3>{escape(stop["name"])}</h3><p>{escape(format_hours(stop["hours"]))}</p>'
                             f'<p>{escape(str(stop.get("restrictions") or "Restrictions not established."))}</p>'
                             f'<p class="notice">{escape(closure_text)}</p><p>{escape(estimate)}</p>'
                             f'<p>Accessibility (published, not surveyed): {escape(" ".join(stop["accessibility"]) if isinstance(stop.get("accessibility"), list) else "not established.")} Fees: not established. Checked {escape(stop["checked_at"])}.</p><p>{links}</p></li>')
            groups.append(f'<h2>{title}</h2><ol>{"".join(items)}</ol>')
        if walk.get("legs"):
            legs = "".join(f'<li>{leg["distance_m"]} m, about {leg["walking_minutes"]} min on foot</li>' for leg in walk["legs"])
            route = (f'<h2>Walking legs</h2><ol>{legs}</ol><p>Total: {walk["distance_m"]} m, about {walk["walking_minutes"]} min walking'
                     + (f', about {walk["total_minutes"]} min with editorial visit estimates' if walk.get("total_minutes") else "")
                     + f'.</p><p class="notice">{escape(walk["legs"][0]["caveat"])}</p><p>{escape(walk["legs"][0]["attribution"])}</p>')
        else:
            route = '<p class="notice">Walking distances and times are not measured. This is a stop sequence, not a navigable route.</p>'
        sections.append(f'<section><h1>{escape(walk["title"])}</h1><p>{escape(walk.get("description", ""))}</p>'
                        '<p class="notice">Not a live opening guarantee. Check official pages before departure.</p>'
                        + "".join(groups) + route + '</section>')
    paths[1].write_text('<!doctype html><html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">'
                        '<title>Wren weekday pilot</title><style>body{margin:0;background:#fafafa;color:#262626;font-family:Georgia,serif}main{max-width:850px;margin:auto;padding:24px}h1{font-size:28px}h2{font-size:21px}h3{font-size:18px}p{line-height:1.55}li{padding:8px 0 18px;border-bottom:1px solid #ccc}a{color:#00756a;overflow-wrap:anywhere}.notice{font-weight:bold}h1,h2,h3{overflow-wrap:anywhere}</style></head><body><main>'
                        + "".join(sections) + '</main></body></html>', encoding="utf-8")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Export sourced stop sequences, without invented route metrics")
    parser.add_argument("--data", type=Path, default=Path("data/london_wren_churches"))
    parser.add_argument("--review", type=Path, default=Path("london-wren-churches/review"))
    parser.add_argument("--output", type=Path, default=Path("london-wren-churches/exports"))
    args = parser.parse_args()
    tables = json.loads((args.data / "tables_reviewed.json").read_text())
    routing = json.loads((args.review / "routing-source.json").read_text())
    router = None
    if routing.get("status") == "selected":
        def router(a: Record, b: Record) -> Record:
            return route_leg(a, b, args.data / "cache", routing)
    walks = build_walks(tables, json.loads((args.review / "walks.json").read_text()), router)
    paths = write_walks(walks, args.output)
    print(json.dumps({"walks": len(walks), "exports": [str(path) for path in paths]}, indent=2))


if __name__ == "__main__":
    main()