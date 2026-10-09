"""Pedestrian legs from the FOSSGIS OSRM foot profile, cached like any other source.

Routes use OpenStreetMap data, (c) OpenStreetMap contributors, ODbL; credit both FOSSGIS and OSM.
"""
import json
from pathlib import Path

from wren_records import Record
from wren_sources import fetch_source

ENDPOINT = "https://routing.openstreetmap.de/routed-foot/route/v1/driving/{a_lon},{a_lat};{b_lon},{b_lat}?overview=false&steps=false"


def leg_url(a: Record, b: Record) -> str:
    return ENDPOINT.format(a_lon=round(a["longitude"], 6), a_lat=round(a["latitude"], 6),
                           b_lon=round(b["longitude"], 6), b_lat=round(b["latitude"], 6))


def parse_leg(payload: Record) -> tuple[int, int]:
    if payload.get("code") != "Ok" or not payload.get("routes"):
        raise ValueError(f"Routing failed: {payload.get('code')}")
    route = payload["routes"][0]
    return round(route["distance"]), max(1, round(route["duration"] / 60))


def route_leg(a: Record, b: Record, cache_dir: Path, routing: Record) -> Record:
    source = fetch_source(leg_url(a, b), cache_dir)
    if source["fetch_status"] != "ok":
        raise ValueError(f"Routing request failed: {source.get('error')}")
    distance, minutes = parse_leg(json.loads((cache_dir / source["document_path"]).read_text()))
    return {"from_place_id": a["place_id"], "to_place_id": b["place_id"], "distance_m": distance,
            "walking_minutes": minutes, "source_id": source["source_id"], "retrieved_at": source["retrieved_at"],
            "routing_source": routing["name"], "attribution": routing["attribution"],
            "caveat": "Between source-reported site coordinates, not verified entrances; foot-profile estimate, no accessibility assessment."}
