import pytest

from review_wren import apply_date_reviews
from tiers_wren import choose_construction


def tables():
    return {"churches": [{"church_id": "a", "name": "A", "cohort": "parish_replacement"}],
            "sources": [{"source_id": "s", "publisher": "en.wikipedia.org"}],
            "claims": [{"claim_id": "seed", "subject_id": "a", "field": "seed_date_range", "value": [1670, 1683],
                        "source_id": "s", "locator": "row", "review_status": "extracted"},
                       {"claim_id": "p", "subject_id": "a", "field": "history_passage", "value": {"text": "x"},
                        "source_id": "s", "locator": "p[1]", "review_status": "extracted"}],
            "events": []}


def review(outcome, value=None, **extra):
    return {"reviewed_at": "2026-10-08", "reviews": [
        {"church_id": "a", "outcome": outcome, "value": value, "evidence_claim_ids": ["p"], "rationale": "read", **extra}]}


def test_verified_interval_becomes_verified_tier_with_publisher_and_seed_alternative():
    data = tables()
    apply_date_reviews(data, review("verified_interval", [1670, 1673], phase="body"))
    row = choose_construction(data)[0]
    assert (row["evidence_tier"], row["earliest_year"], row["latest_year"]) == ("verified", 1670, 1673)
    assert row["verified_source"] == ["en.wikipedia.org"] and row["alternatives"] == [[1670, 1683]]
    assert data["events"][0]["date_role"] == "construction_interval"


def test_conflict_makes_tier_disputed_without_an_event():
    data = tables()
    apply_date_reviews(data, review("conflict", [None, 1676]))
    row = choose_construction(data)[0]
    assert row["evidence_tier"] == "disputed" and row["alternatives"] == [[None, 1676]]
    assert data["events"] == []


def test_milestone_is_verified_but_not_an_interval():
    data = tables()
    apply_date_reviews(data, review("verified_milestone", [1678, 1678], date_role="reported_rebuild_year"))
    assert data["events"][0]["date_role"] == "reported_rebuild_year"
    assert choose_construction(data)[0]["evidence_tier"] == "reported"


def test_unresolved_adds_nothing_and_foreign_evidence_is_rejected():
    data = tables()
    apply_date_reviews(data, review("unresolved"))
    assert len(data["claims"]) == 2
    data["claims"][1]["subject_id"] = "other"
    with pytest.raises(ValueError):
        apply_date_reviews(data, review("verified_interval", [1670, 1673]))


def test_loss_reason_review_sets_mechanism_on_matching_events_only():
    from review_wren import apply_loss_reasons
    from analyse_wren import loss_mechanism
    data = tables()
    data["events"] = [{"event_id": "d", "church_id": "a", "kind": "demolition", "claim_ids": ["seed"]},
                      {"event_id": "r", "church_id": "a", "kind": "restoration", "claim_ids": ["seed"]}]
    apply_loss_reasons(data, {"reviewed_at": "2026-10-08", "reasons": [
        {"church_id": "a", "kinds": ["demolition"], "mechanism": "structural_safety",
         "evidence_claim_ids": ["p"], "rationale": "found unsafe"}]})
    assert loss_mechanism(data["events"][0]) == "structural_safety"
    assert "mechanism" not in data["events"][1]


def test_cost_must_appear_in_evidence_passage():
    from review_wren import apply_costs
    data = tables()
    data["claims"][1]["value"] = {"text": "rebuilt at a cost of £4,466."}
    apply_costs(data, {"reviewed_at": "2026-10-08", "costs": [
        {"church_id": "a", "evidence_claim_id": "p", "pounds": 4466, "shillings": 10, "scope": "rebuilding"}]})
    assert data["claims"][-1]["value"]["decimal_pounds"] == 4466.5
    with pytest.raises(ValueError):
        apply_costs(data, {"reviewed_at": "2026-10-08", "costs": [
            {"church_id": "a", "evidence_claim_id": "p", "pounds": 9999, "scope": "rebuilding"}]})


def test_listed_fabric_reads_official_wording():
    from analyse_wren import listed_fabric
    data = tables()
    data["claims"].append({"claim_id": "he", "subject_id": "a", "field": "official_entry_passage", "source_id": "s",
                           "value": {"text": "1670-83 by Wren. Interior destroyed in World War II and reconstructed in near facsimile."}})
    assert listed_fabric(data)[0]["fabric_flag"] == "interior_reconstructed_in_facsimile"
