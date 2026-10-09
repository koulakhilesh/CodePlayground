from copy import deepcopy
import json

from bs4 import BeautifulSoup
import pytest

from walk_wren import build_walks, validate_walk, write_walks


def data():
    return {"churches": [{"church_id": "c1", "name": "Church", "cohort": "parish_replacement"}],
            "places": [{"place_id": "p1", "church_id": "c1", "role": "historical_site", "latitude": 51.5, "longitude": -0.1}],
            "sources": [{"source_id": "s1", "url": "https://example.org/visit"}],
            "claims": [{"claim_id": "q1", "subject_id": "c1", "source_id": "s1", "review_status": "verified"}],
            "visits": [{"visit_id": "v1", "place_id": "p1", "access_type": "interior", "hours": None,
                        "restrictions": "Check before visiting", "closure": None, "fee": None,
                        "accessibility": None, "checked_at": "2026-10-08", "claim_ids": ["q1"]}]}


def walk():
    return {"walk_id": "w1", "title": "Pilot", "theme": "interiors", "checked_at": "2026-10-08",
            "stops": [{"place_id": "p1", "visit_id": "v1", "access_type": "interior", "claim_ids": ["q1"],
                       "visit_minutes": 20, "duration_basis": "editorial_estimate"}],
            "optional_stops": [], "legs": []}


def test_unmeasured_walk_keeps_unknown_access_information():
    original = data()
    snapshot = deepcopy(original)
    result = build_walks(original, [walk()])[0]
    assert result["walking_minutes"] is None
    assert result["total_minutes"] is None
    assert result["stops"][0]["hours"] is None
    assert result["stops"][0]["accessibility"] is None
    assert result["stops"][0]["source_urls"] == ["https://example.org/visit"]
    assert original == snapshot


def test_missing_stop_and_wrong_claim_ownership_are_rejected():
    candidate = walk()
    candidate["stops"][0]["place_id"] = "missing"
    assert validate_walk(candidate, data())
    original = data()
    original["claims"][0]["subject_id"] = "other"
    assert any("ownership" in error for error in validate_walk(walk(), original))


def test_closed_interior_cannot_be_a_required_stop():
    original = data()
    original["visits"][0]["closure"] = {"status": "announced_closure", "start_approximate": "2026-10-12", "reopening_date": None}
    assert any("closure" in error for error in validate_walk(walk(), original))
    candidate = walk()
    candidate["optional_stops"] = candidate.pop("stops")
    candidate["stops"] = []
    assert validate_walk(candidate, original) == []
    result = build_walks(original, [candidate])[0]
    assert result["optional_stops"][0]["closure"]["reopening_date"] is None


def test_unsourced_walking_metrics_are_rejected():
    candidate = walk()
    candidate["legs"] = [{"distance_m": 400, "duration_s": 300, "profile": "straight_line"}]
    assert any("pedestrian" in error for error in validate_walk(candidate, data()))


def test_unknown_or_disputed_evidence_cannot_support_visiting():
    original = data()
    original["claims"][0]["review_status"] = "disputed"
    with pytest.raises(ValueError, match="verified"):
        build_walks(original, [walk()])


def test_scope_is_retained_in_pilot_preview(tmp_path):
    original = data()
    original["visits"][0]["hours"] = {"scope": "Cafe", "days": ["Monday"], "opens": "07:30", "closes": "16:00", "timezone": "Europe/London"}
    result = build_walks(original, [walk()])
    write_walks(result, tmp_path)
    saved = json.loads((tmp_path / "pilot_walks.json").read_text())
    assert saved[0]["stops"][0]["hours"]["scope"] == "Cafe"
    document = BeautifulSoup((tmp_path / "pilot_walk.html").read_text(), "html.parser")
    assert "Cafe" in document.get_text()
    assert "not measured" in document.get_text()
    assert document.select_one('a[href="https://example.org/visit"]') is not None

def test_router_adds_legs_and_totals_with_caveat():
    from routing_wren import leg_url, parse_leg
    original = data()
    original["places"].append({"place_id": "p2", "church_id": "c1", "role": "historical_site", "latitude": 51.51, "longitude": -0.09})
    original["visits"].append(dict(original["visits"][0], visit_id="v2", place_id="p2"))
    candidate = walk()
    candidate["stops"].append({"place_id": "p2", "visit_id": "v2", "access_type": "interior", "claim_ids": ["q1"],
                               "visit_minutes": 15, "duration_basis": "editorial_estimate"})
    distance, minutes = parse_leg({"code": "Ok", "routes": [{"distance": 812.4, "duration": 590}]})

    def router(a, b):
        return {"from_place_id": a["place_id"], "to_place_id": b["place_id"], "distance_m": distance,
                "walking_minutes": minutes, "caveat": "site coordinates", "attribution": "OSM"}

    result = build_walks(original, [candidate], router)[0]
    assert (result["distance_m"], result["walking_minutes"], result["total_minutes"]) == (812, 10, 45)
    assert result["route_status"] == "routed_between_site_coordinates"
    assert "-0.1,51.5;-0.09,51.51" in leg_url(original["places"][0], original["places"][1])
    with pytest.raises(ValueError):
        parse_leg({"code": "NoRoute"})
