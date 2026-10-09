import json
from bs4 import BeautifulSoup

from analyse_wren import build_map_points, summarise_history, write_analysis


def tables():
    return {"churches": [{"church_id": "c1", "name": "Church", "cohort": "parish_replacement"},
                         {"church_id": "c2", "name": "Cathedral", "cohort": "cathedral"}],
            "claims": [{"claim_id": "q1", "subject_id": "c1", "field": "construction_range",
                        "value": [1683, 1687], "source_id": "s1", "review_status": "verified"},
                       {"claim_id": "q2", "subject_id": "c1", "field": "seed_coordinates",
                        "value": [51.5, -0.1], "source_id": "s1", "review_status": "extracted"}],
            "sources": [{"source_id": "s1", "url": "https://example.org/history"}],
            "events": [{"event_id": "e1", "church_id": "c1", "kind": "construction", "phase": "body",
                        "earliest_year": 1683, "latest_year": 1687, "claim_ids": ["q1"]}],
            "places": [{"place_id": "p1", "church_id": "c1", "role": "historical_site",
                        "latitude": 51.5, "longitude": -0.1, "claim_ids": ["q2"]}]}


def test_verified_body_interval_produces_starts_completions_and_elapsed_span():
    summary = summarise_history(tables())
    assert summary["starts"] == [{"year": 1683, "church_id": "c1", "event_id": "e1"}]
    assert summary["completions"] == [{"year": 1687, "church_id": "c1", "event_id": "e1"}]
    assert summary["durations"][0]["elapsed_years"] == 4


def test_restoration_partial_loss_and_cathedral_are_not_parish_completions():
    data = tables()
    data["events"] = [
        {"event_id": "restore", "church_id": "c1", "kind": "restoration", "phase": "body",
         "earliest_year": 1955, "latest_year": 1955, "claim_ids": ["q1"]},
        {"event_id": "loss", "church_id": "c1", "kind": "partial_demolition", "phase": "body",
         "earliest_year": 1871, "latest_year": 1871, "claim_ids": ["q1"]},
        {"event_id": "cathedral", "church_id": "c2", "kind": "construction", "phase": "cathedral",
         "earliest_year": 1675, "latest_year": 1711, "claim_ids": ["q1"]}]
    summary = summarise_history(data)
    assert summary["completions"] == []
    assert summary["losses"][0]["kind"] == "partial_demolition"


def test_disputed_evidence_and_unsourced_events_are_not_plotted_as_verified():
    data = tables()
    data["claims"][0]["review_status"] = "disputed"
    assert summarise_history(data)["timeline"] == []
    data["events"][0]["claim_ids"] = []
    assert summarise_history(data)["timeline"] == []


def test_missing_dates_are_not_imputed():
    data = tables()
    data["events"][0]["earliest_year"] = None
    assert summarise_history(data)["durations"] == []


def test_map_points_label_unreviewed_location_and_deduplicate_seed_sites():
    data = tables()
    data["places"].append({**data["places"][0], "place_id": "p2"})
    points = build_map_points(data)
    assert len(points) == 1
    assert points[0]["location_status"] == "extracted"
    assert points[0]["role"] == "historical_site"
    assert points[0]["source_urls"] == ["https://example.org/history"]


def test_offline_exports_contain_review_status_and_no_open_now_claims(tmp_path):
    paths = write_analysis(tables(), tmp_path)
    assert {path.name for path in paths} >= {"cohort_map.html", "reviewed_timeline.html", "analysis_summary.json", "church_register.csv"}
    summary = json.loads((tmp_path / "analysis_summary.json").read_text())
    assert summary["reviewed_event_count"] == 1
    assert summary["candidate_count"] == 2
    assert "extracted" in (tmp_path / "church_register.csv").read_text()
    assert "open_now" not in json.dumps(summary)


def test_export_places_evidence_caption_in_wrapping_html_not_svg_title(tmp_path):
    write_analysis(tables(), tmp_path)
    document = BeautifulSoup((tmp_path / "cohort_map.html").read_text(), "html.parser")
    assert document.find("meta", attrs={"name": "viewport"}) is not None
    assert document.find("h1").get_text() == "Wren-associated sites"
    assert "not visitor entrances" in document.find("header").get_text()


def test_construction_milestone_does_not_become_zero_year_duration():
    data = tables()
    data["events"][0].update(earliest_year=1672, latest_year=1672, date_role="foundation_milestone")
    summary = summarise_history(data)
    assert len(summary["timeline"]) == 1
    assert summary["durations"] == []
    assert summary["completions"] == []

def test_tiered_history_labels_losses_by_mechanism_and_tier():
    from analyse_wren import tiered_history
    data = tables()
    data["claims"].append({"claim_id": "cell", "subject_id": "c1", "field": "seed_cells", "value": {},
                           "source_id": "s1", "review_status": "extracted"})
    data["events"] += [
        {"event_id": "u", "church_id": "c1", "kind": "demolition", "phase": "body", "earliest_year": 1876,
         "latest_year": 1876, "claim_ids": ["cell"], "evidence_tier": "reported",
         "reported_reason": "Union of Benefices Act (section classification)"},
        {"event_id": "w", "church_id": "c1", "kind": "destruction", "phase": "body", "earliest_year": 1940,
         "latest_year": 1940, "claim_ids": ["q1"]},
        {"event_id": "s", "church_id": "c1", "kind": "demolition", "phase": "body", "earliest_year": 1900,
         "latest_year": 1900, "claim_ids": ["cell"], "evidence_tier": "reported",
         "reported_reason": "judged structurally unsafe in 1892"}]
    result = tiered_history(data)
    by_event = {(row["mechanism"], row["evidence_tier"]) for row in result["losses"]}
    assert by_event == {("union_of_benefices", "reported"), ("war_destruction", "verified"),
                        ("structural_safety", "reported")}
    assert result["construction_tiers"] == {"verified": 1}


def test_undated_loss_is_merged_into_dated_loss_with_same_cause():
    from analyse_wren import tiered_history
    data = tables()
    data["events"] += [
        {"event_id": "seed", "church_id": "c1", "kind": "destruction", "phase": "body", "earliest_year": None,
         "latest_year": None, "claim_ids": [], "reported_reason": "Destroyed in the Blitz"},
        {"event_id": "dated", "church_id": "c1", "kind": "demolition", "phase": "ruins", "earliest_year": 1940,
         "latest_year": 1940, "claim_ids": [], "mechanism": "war_destruction"}]
    losses = tiered_history(data)["losses"]
    assert [(row["mechanism"], row["earliest_year"]) for row in losses] == [("war_destruction", 1940)]
