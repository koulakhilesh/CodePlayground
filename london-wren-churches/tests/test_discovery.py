from copy import deepcopy
import json

from bs4 import BeautifulSoup
import pytest

from discover_wren import build_graph, write_graph


def data():
    return {"churches": [{"church_id": "c1", "name": "First", "cohort": "parish_replacement"},
                         {"church_id": "c2", "name": "Second", "cohort": "parish_repair"},
                         {"church_id": "c3", "name": "Unconnected", "cohort": "unresolved"}],
            "sources": [{"source_id": "s1", "url": "https://example.org/history"}],
            "claims": [{"claim_id": "q1", "subject_id": "c1", "field": "comparison",
                        "value": {"related_church_ids": ["c2"]}, "source_id": "s1",
                        "review_status": "verified", "locator": "p1"}], "visits": []}


def connection():
    return {"connection_id": "e1", "from_id": "c1", "to_id": "c2", "relation": "reported_similarity",
            "theme": "interiors_and_domes", "evidence_kind": "direct_statement", "claim_ids": ["q1"],
            "explanation": "The source compares the two.", "caveat": "Not influence or route advice."}


def test_graph_exports_evidence_and_missing_coverage_without_mutating_inputs():
    tables = data()
    snapshot = deepcopy(tables)
    graph = build_graph(tables, [connection()])
    assert [node["church_id"] for node in graph["nodes"]] == ["c1", "c2"]
    assert graph["edges"][0]["sources"][0]["url"] == "https://example.org/history"
    assert graph["edges"][0]["sources"][0]["locator"] == "p1"
    assert graph["coverage"]["unconnected_candidate_ids"] == ["c3"]
    assert "travelling_stone" in graph["coverage"]["empty_themes"]
    assert tables == snapshot


@pytest.mark.parametrize("field,value", [("to_id", "missing"), ("claim_ids", []),
                                          ("claim_ids", ["missing"]), ("caveat", ""),
                                          ("theme", "invented_theme")])
def test_incomplete_or_unsourced_edges_are_rejected(field, value):
    edge = connection()
    edge[field] = value
    with pytest.raises(ValueError):
        build_graph(data(), [edge])


def test_direct_statement_must_name_the_other_endpoint():
    tables = data()
    tables["claims"][0]["value"] = {"related_church_ids": ["c3"]}
    with pytest.raises(ValueError, match="endpoint"):
        build_graph(tables, [connection()])


def test_descriptive_comparison_requires_verified_evidence_for_both_endpoints():
    tables = data()
    edge = {**connection(), "evidence_kind": "descriptive_comparison"}
    with pytest.raises(ValueError, match="both"):
        build_graph(tables, [edge])
    tables["claims"].append({**tables["claims"][0], "claim_id": "q2", "subject_id": "c2"})
    edge["claim_ids"] = ["q1", "q2"]
    assert build_graph(tables, [edge])["edges"][0]["evidence_kind"] == "descriptive_comparison"
    tables["claims"][1]["review_status"] = "disputed"
    with pytest.raises(ValueError, match="verified"):
        build_graph(tables, [edge])


def test_graph_retains_closure_notice_without_inferring_access():
    tables = data()
    tables["places"] = [{"place_id": "p1", "church_id": "c1"}]
    tables["visits"] = [{"place_id": "p1", "closure": {"start_approximate": "2026-10-12", "reopening_date": None}}]
    node = build_graph(tables, [connection()])["nodes"][0]
    assert node["closure_notices"][0]["reopening_date"] is None
    assert "open_now" not in node


def test_export_is_deterministic_and_has_theme_filter_and_sources(tmp_path):
    graph = build_graph(data(), [connection()])
    write_graph(graph, tmp_path)
    initial = (tmp_path / "discovery.json").read_bytes()
    write_graph(graph, tmp_path)
    assert initial == (tmp_path / "discovery.json").read_bytes()
    saved = json.loads(initial)
    assert len(saved["edges"]) == 1
    document = BeautifulSoup((tmp_path / "discovery_graph.html").read_text(), "html.parser")
    assert len(document.select("select#theme option")) == 6
    assert document.select_one('a[href="https://example.org/history"]')
    assert "not walking directions" in document.get_text()

def test_parish_unions_and_relocations_fill_themes_with_tier_labels(tmp_path):
    tables = data()
    tables["claims"].append({"claim_id": "u", "subject_id": "p1", "field": "parish_union", "value": {},
                             "source_id": "s1", "review_status": "extracted", "locator": "row 1"})
    tables["parishes"] = [{"parish_id": "p1", "name": "St Lost"}]
    tables["events"] = [
        {"event_id": "m", "church_id": "c1", "parish_id": "p1", "kind": "parish_merger", "claim_ids": ["u"],
         "evidence_tier": "reported"},
        {"event_id": "r", "church_id": "c2", "kind": "relocation", "phase": "fabric", "destination": "Fulton, Missouri",
         "earliest_year": 1964, "latest_year": 1964, "claim_ids": ["u"], "evidence_tier": "reported"}]
    graph = build_graph(tables, [])
    assert graph["parish_unions"][0]["parishes"] == [{"name": "St Lost", "evidence_tier": "reported"}]
    assert graph["relocations"][0]["destination"] == "Fulton, Missouri"
    assert not {"lost_churches", "travelling_stone"} & set(graph["coverage"]["empty_themes"])
    html = write_graph(graph, tmp_path)[1].read_text()
    assert "St Lost (reported)" in html and "Fulton, Missouri" in html
