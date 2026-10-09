from copy import deepcopy
import json

import pytest

from collect_wren import extract_reference, reference_targets
from review_wren import apply_review, coverage_report, gap_report
from wren_records import resolve_claims


def sample_tables():
    return {"churches": [{"church_id": "c1", "name": "Church", "cohort": "unresolved", "aliases": [], "seed_ids": ["r1"]},
                         {"church_id": "c2", "name": "Cathedral", "cohort": "unresolved", "aliases": [], "seed_ids": ["r2"]}],
            "sources": [{"source_id": "s1", "fetch_status": "ok"}],
            "claims": [{"claim_id": "q1", "subject_id": "c1", "field": "completion",
                        "value": 1679, "source_id": "s1", "locator": "p1", "review_status": "extracted"}],
            "events": [], "places": []}


def test_review_requires_explicit_cohort_decision(tmp_path):
    tables = sample_tables()
    original = deepcopy(tables)
    (tmp_path / "identities.json").write_text(json.dumps([
        {"candidate_id": "c2", "church_id": "c2", "cohort": "cathedral",
         "rationale": "Cathedral kept separate", "reviewed_at": "2026-10-08"}]))
    reviewed = apply_review(tables, tmp_path)
    assert reviewed["churches"][0]["cohort"] == "unresolved"
    assert reviewed["churches"][1]["cohort"] == "cathedral"
    assert tables == original
    assert reviewed["claims"][0]["review_status"] == "extracted"


def test_review_rejects_nonexistent_identity(tmp_path):
    (tmp_path / "identities.json").write_text(json.dumps([
        {"candidate_id": "missing", "church_id": "missing", "cohort": "cathedral",
         "rationale": "Wrong key", "reviewed_at": "2026-10-08"}]))
    with pytest.raises(ValueError, match="candidate"):
        apply_review(sample_tables(), tmp_path)


def test_coverage_counts_missing_fields_not_as_zero_values():
    report = coverage_report(sample_tables())
    assert report["churches"] == 2
    assert report["fields"]["completion"] == {"verified": 0, "extracted": 1, "disputed": 0, "rejected": 0, "missing": 1}
    assert report["cohorts"] == {"unresolved": 2}
    assert report["fields"]["visitor_hours"]["missing"] == 2


def test_different_passages_are_not_automatically_date_conflicts():
    claims = [{"claim_id": "q1", "subject_id": "c1", "field": "history_passage", "value": {"text": "Body built in 1679"}, "review_status": "extracted"},
              {"claim_id": "q2", "subject_id": "c1", "field": "history_passage", "value": {"text": "Bombed in 1940"}, "review_status": "extracted"}]
    assert all(claim["review_status"] == "extracted" for claim in resolve_claims(claims, []))


def test_reference_discovery_accepts_only_official_heritage_domain():
    links = [
        {"subject_id": "c1", "url": "https://historicengland.org.uk/listing/the-list/list-entry/1285320?section=official-list-entry", "label": "Entry"},
        {"subject_id": "c1", "url": "https://historicengland.org.uk/listing/the-list/list-entry/1285320", "label": "Duplicate"},
        {"subject_id": "c1", "url": "https://historicengland.org.uk.evil.test/listing/the-list/list-entry/1285320"},
        {"subject_id": "c2", "url": "https://example.org/history"},
    ]
    targets = reference_targets(links, [])
    assert len(targets) == 1
    assert targets[0]["url"] == "https://historicengland.org.uk/listing/the-list/list-entry/1285320"
    assert targets[0]["subject_id"] == "c1"


def test_reference_passages_keep_locator_and_do_not_verify_themselves():
    html = '<main><h1>Church of Test</h1><h3>Details</h3><p>1672 to 87 by Wren. Tower restored later.</p><h3>Legal</h3><p>Listed building.</p></main>'
    evidence = extract_reference(html, "c1", "s1")
    assert any("1672" in claim["value"]["text"] for claim in evidence["claims"])
    assert all(claim["review_status"] == "extracted" for claim in evidence["claims"])
    assert all(claim["source_id"] == "s1" and claim["locator"] for claim in evidence["claims"])


def test_contextual_reference_is_not_labelled_church_entry():
    evidence = extract_reference("<main><h3>Details</h3><p>Fishmongers Hall, 1831 to 34.</p></main>", "c1", "s1", relationship="context_only")
    assert evidence["claims"][0]["field"] == "context_passage"
    assert evidence["claims"][0]["relationship"] == "context_only"


@pytest.mark.parametrize("cohort", ["parish_repair", "parish_nonfire_rebuilding"])
def test_repair_cohort_retains_work_scope_and_supporting_evidence(tmp_path, cohort):
    (tmp_path / "identities.json").write_text(json.dumps([
        {"candidate_id": "c1", "church_id": "c1", "cohort": cohort,
         "wren_work": "repair_and_new_tower", "evidence_claim_ids": ["q1"],
         "rationale": "Existing body repaired, new tower separately constructed",
         "reviewed_at": "2026-10-08"}]))
    reviewed = apply_review(sample_tables(), tmp_path)
    church = reviewed["churches"][0]
    assert church["cohort"] == cohort
    assert church["wren_work"] == "repair_and_new_tower"
    assert church["identity_claim_ids"] == ["q1"]
    assert coverage_report(reviewed)["cohorts"] == {cohort: 1, "unresolved": 1}


def test_identity_evidence_must_belong_to_reviewed_church(tmp_path):
    (tmp_path / "identities.json").write_text(json.dumps([
        {"candidate_id": "c2", "church_id": "c2", "cohort": "parish_repair",
         "evidence_claim_ids": ["q1"], "rationale": "Evidence belongs elsewhere",
         "reviewed_at": "2026-10-08"}]))
    with pytest.raises(ValueError, match="identity evidence"):
        apply_review(sample_tables(), tmp_path)


def test_visitor_source_is_not_labelled_architectural_entry():
    html = '<main><h2>Visit</h2><p>Open Monday to Friday, 10am to 4pm, except services.</p></main>'
    evidence = extract_reference(html, "c1", "s1", relationship="visitor_information")
    assert evidence["claims"][0]["field"] == "visitor_source_passage"
    assert evidence["claims"][0]["review_status"] == "extracted"
    assert "except services" in evidence["claims"][0]["value"]["text"]


def test_visitor_extraction_keeps_small_heading_closures_and_footer_hours():
    html = '<main><h5>Closed from about 12 October 2026 for nine months.</h5></main><footer><p>Monday-Friday 10:30am-3:30pm</p></footer>'
    evidence = extract_reference(html, "c1", "s1", relationship="visitor_information")
    texts = [claim["value"]["text"] for claim in evidence["claims"]]
    assert any("Closed from about" in text for text in texts)
    assert any("10:30am" in text for text in texts)


def test_reviewed_dataset_includes_visitor_records_with_valid_references(tmp_path):
    tables = sample_tables()
    tables["places"] = [{"place_id": "p1", "church_id": "c1", "role": "historical_site"}]
    visit = {"visit_id": "v1", "place_id": "p1", "access_type": "unknown", "hours": None,
             "accessibility": None, "checked_at": "2026-10-08", "claim_ids": ["q1"]}
    (tmp_path / "visits.json").write_text(json.dumps([visit]))
    reviewed = apply_review(tables, tmp_path)
    assert reviewed["visits"] == [visit]


def test_gap_report_distinguishes_collected_evidence_from_reviewed_facts():
    tables = sample_tables()
    tables["claims"].extend([
        {"claim_id": "q2", "subject_id": "c1", "field": "history_passage", "value": {"text": "Cost 5000"}, "review_status": "extracted"},
        {"claim_id": "q3", "subject_id": "c2", "field": "construction_range", "value": [1675, 1711], "review_status": "verified"}])
    report = gap_report(tables)
    assert report["fields"]["cost"]["verified_churches"] == 0
    assert report["fields"]["cost"]["needs_review_ids"] == ["c1", "c2"]
    assert report["fields"]["construction_dates"]["verified_churches"] == 1
    assert report["fields"]["construction_dates"]["needs_review_ids"] == ["c1"]
    assert report["verified_event_churches"] == 0


def test_gap_report_counts_events_only_when_all_evidence_is_verified_and_owned():
    tables = sample_tables()
    tables["claims"][0]["review_status"] = "verified"
    tables["events"] = [{"event_id": "e1", "church_id": "c1", "claim_ids": ["q1"]},
                        {"event_id": "e2", "church_id": "c2", "claim_ids": ["q1"]}]
    assert gap_report(tables)["verified_event_churches"] == 1