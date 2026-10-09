from copy import deepcopy

import pytest

from wren_records import make_id, resolve_claims, validate_tables


def records():
    return {
        "churches": [{"church_id": "c1", "name": "Test", "cohort": "unresolved"}],
        "sources": [{"source_id": "s1", "url": "https://example.org/history"}],
        "claims": [{"claim_id": "q1", "subject_id": "c1", "field": "completion",
                    "value": 1679, "source_id": "s1", "locator": "p1",
                    "review_status": "extracted"}],
        "places": [{"place_id": "p1", "church_id": "c1", "role": "historical_site",
                    "latitude": 51.5, "longitude": -0.1, "claim_ids": ["q1"]}],
        "events": [{"event_id": "e1", "church_id": "c1", "kind": "construction",
                    "earliest_year": 1672, "latest_year": 1679, "claim_ids": ["q1"]}],
        "visits": [{"visit_id": "v1", "place_id": "p1", "access_type": "unknown",
                    "hours": None, "accessibility": None, "claim_ids": []}],
    }


def test_identity_namespaces_do_not_collide():
    assert make_id("church", "123") == make_id("church", "123")
    assert make_id("church", "123") != make_id("source", "123")
    assert make_id("church", "a:b") != make_id("church:a", "b")


def test_valid_unknown_information_is_not_invented():
    tables = records()
    original = deepcopy(tables)
    assert validate_tables(tables) == []
    assert tables == original
    assert tables["visits"][0]["hours"] is None


@pytest.mark.parametrize("table,field,value,fragment", [
    ("places", "latitude", 95, "latitude"),
    ("places", "longitude", float("nan"), "longitude"),
    ("places", "church_id", "missing", "church_id"),
    ("claims", "source_id", "missing", "source_id"),
    ("claims", "subject_id", "missing", "subject_id"),
    ("claims", "review_status", "certain", "review_status"),
    ("events", "earliest_year", 1700, "date range"),
    ("events", "claim_ids", ["missing"], "claim_ids"),
])
def test_invalid_records_are_reported(table, field, value, fragment):
    tables = records()
    tables[table][0][field] = value
    assert any(fragment in error for error in validate_tables(tables))


def test_duplicate_ids_are_rejected():
    tables = records()
    tables["churches"].append(deepcopy(tables["churches"][0]))
    assert any("duplicate" in error for error in validate_tables(tables))


def test_conflicts_preserve_evidence_without_verifying_it():
    claims = records()["claims"]
    claims.append({**claims[0], "claim_id": "q2", "value": 1687})
    original = deepcopy(claims)
    resolved = resolve_claims(claims, [])
    assert [claim["value"] for claim in resolved] == [1679, 1687]
    assert all(claim["review_status"] == "disputed" for claim in resolved)
    assert claims == original


def test_review_requires_rationale_and_correct_claim_ownership():
    claims = records()["claims"]
    decision = {"subject_id": "c1", "field": "completion", "selected_claim_ids": ["q1"],
                "rejected_claim_ids": [], "rationale": "", "reviewed_at": "2026-10-08"}
    with pytest.raises(ValueError, match="rationale"):
        resolve_claims(claims, [decision])
    decision["rationale"] = "Checked the cited record"
    decision["subject_id"] = "other"
    with pytest.raises(ValueError, match="ownership"):
        resolve_claims(claims, [decision])


def test_explicit_review_does_not_destroy_alternative_claim():
    claims = records()["claims"]
    claims.append({**claims[0], "claim_id": "q2", "value": 1687})
    decision = {"subject_id": "c1", "field": "completion", "selected_claim_ids": ["q1"],
                "rejected_claim_ids": [], "rationale": "Body completion only",
                "reviewed_at": "2026-10-08"}
    resolved = resolve_claims(claims, [decision])
    assert resolved[0]["review_status"] == "verified"
    assert resolved[1]["review_status"] == "disputed"
    assert resolved[0]["review_rationale"] == "Body completion only"