from tiers_wren import choose_construction, derive_seed_events, listing_agreement


def seed_claim(church_id, section, cells, date_range=None):
    return [{"claim_id": f"{church_id}_section", "subject_id": church_id, "field": "seed_section", "value": section,
             "source_id": "s1", "locator": "row", "review_status": "extracted"},
            {"claim_id": f"{church_id}_cells", "subject_id": church_id, "field": "seed_cells", "value": cells,
             "source_id": "s1", "locator": "row", "review_status": "extracted"},
            {"claim_id": f"{church_id}_dates", "subject_id": church_id, "field": "seed_date_range", "value": date_range,
             "source_id": "s1", "locator": "row", "review_status": "extracted"}]


def tables(*claim_groups, cohorts=None):
    claims = [claim for group in claim_groups for claim in group]
    ids = sorted({claim["subject_id"] for claim in claims})
    return {"churches": [{"church_id": identifier, "name": identifier, "cohort": (cohorts or {}).get(identifier, "parish_replacement")}
                         for identifier in ids], "claims": claims, "events": [], "sources": [{"source_id": "s1"}]}


def kinds(events):
    return sorted((event["church_id"], event["kind"], event.get("phase"), event["earliest_year"], event["latest_year"]) for event in events)


def test_demolition_patterns_and_reasons_are_reported_not_verified():
    data = tables(seed_claim("a", "Demolished due to the Union of Benefices Act (chronological order)", {"Comment": "demolished in 1868"}, [1681, 1687]),
                  seed_claim("b", "Demolished for other reasons (chronological order)",
                             {"Demolition": "demolished between 1841 and 1846", "Reason": "to improve the site of the Royal Exchange"}, [1670, 1675]),
                  seed_claim("c", "Tower remaining", {"Comment": "Body of the church demolished in 1871. Tower surrounded by small garden"}, [1686, 1694]))
    events, unparsed = derive_seed_events(data)
    losses = [event for event in events if event["kind"] != "construction"]
    assert kinds(losses) == [("a", "demolition", "body", 1868, 1868), ("b", "demolition", "body", 1841, 1846),
                             ("c", "partial_demolition", "body", 1871, 1871)]
    assert next(event for event in losses if event["church_id"] == "a")["reported_reason"] == "Union of Benefices Act (section classification)"
    assert next(event for event in losses if event["church_id"] == "b")["reported_reason"] == "to improve the site of the Royal Exchange"
    assert all(event["evidence_tier"] == "reported" for event in events)
    assert unparsed == []


def test_war_restoration_relocation_and_alteration_patterns():
    data = tables(seed_claim("a", "Substantially rebuilt after the Blitz", {"Comment": "restored in 1966–8"}),
                  seed_claim("b", "Stones re-used", {"Comment": "Ruined in 1940, and the stones transported to Fulton, Missouri in 1964. Rebuilt as a memorial"}),
                  seed_claim("c", "Churches built outside the City of London", {"Comment": "Destroyed in 1940; restored in 1947–54 after the Blitz"}),
                  seed_claim("d", "Substantially altered before the Blitz", {"Comment": "altered in 1787–88 and 1826–27"}),
                  seed_claim("e", "Tower remaining", {"Comment": "Destroyed in the Blitz. The tower is private dwelling"}),
                  seed_claim("f", "Destroyed in the Blitz", {"Demolition": "1962"}))
    events, unparsed = derive_seed_events(data)
    assert ("a", "restoration", "body", 1966, 1968) in kinds(events)
    assert ("a", "damage", "body", None, None) in kinds(events)
    assert ("b", "destruction", "body", 1940, 1940) in kinds(events)
    assert ("b", "relocation", "fabric", 1964, 1964) in kinds(events)
    assert ("c", "destruction", "body", 1940, 1940) in kinds(events)
    assert ("c", "restoration", "body", 1947, 1954) in kinds(events)
    assert ("d", "alteration", "body", 1787, 1788) in kinds(events)
    assert ("d", "alteration", "body", 1826, 1827) in kinds(events)
    assert ("e", "destruction", "body", None, None) in kinds(events)
    assert ("f", "destruction", "body", None, None) in kinds(events)
    ruins = next(event for event in events if event["church_id"] == "f" and event["earliest_year"] == 1962)
    assert ruins["date_role"] == "reported_loss_year_scope_unclear"
    assert unparsed == []


def test_unrecognised_comments_are_reported_for_manual_review():
    data = tables(seed_claim("a", "Interior refurbished by Christopher Wren", {"Comment": "Wren's wooden altar was discovered in a museum"}))
    events, unparsed = derive_seed_events(data)
    assert [event["kind"] for event in events] == []
    assert unparsed == [{"church_id": "a", "text": "Wren's wooden altar was discovered in a museum"}]


def test_construction_events_keep_unspecified_scope():
    events, _ = derive_seed_events(tables(seed_claim("a", "Survived in original form", {}, [1670, 1679])))
    assert kinds(events) == [("a", "construction", "seed_scope_unspecified", 1670, 1679)]
    assert events[0]["date_role"] == "construction_interval_scope_unspecified"


def listing(church_id, text, relationship="unreviewed_reference"):
    return {"claim_id": f"{church_id}_listing", "subject_id": church_id, "field": "official_entry_passage",
            "value": {"section": "Details", "text": text}, "source_id": "s2", "locator": "block", "review_status": "extracted",
            "relationship": relationship}


def test_listing_agreement_detects_matching_differing_and_absent_ranges():
    data = tables(seed_claim("a", "Survived in original form", {}, [1670, 1679]),
                  seed_claim("b", "Survived in original form", {}, [1686, 1690]),
                  seed_claim("c", "Survived in original form", {}, [1679, 1682]),
                  seed_claim("d", "Survived in original form", {}, [1682, 1687]))
    data["claims"] += [listing("a", "4.1.50. I 2. 1670 to 79, by Wren. Simple body"),
                       listing("b", "GV 2. 1686-95 by Wren. Simple, rectangular body"),
                       listing("c", "Late C17, by Wren, incorporating earlier work"),
                       listing("d", "1682 to 87, by Sir Christopher Wren.", relationship="context_only")]
    result = {row["church_id"]: row for row in listing_agreement(data)}
    assert result["a"]["status"] == "agrees" and result["a"]["listing_range"] == [1670, 1679]
    assert result["b"]["status"] == "differs" and result["b"]["listing_range"] == [1686, 1695]
    assert result["c"]["status"] == "no_listing_range"
    assert result["d"]["status"] == "no_listing_range"


def test_choose_construction_prefers_verified_then_agreement_and_flags_disputes():
    data = tables(seed_claim("a", "Survived in original form", {}, [1683, 1687]),
                  seed_claim("b", "Survived in original form", {}, [1670, 1679]),
                  seed_claim("c", "Survived in original form", {}, [1686, 1690]),
                  seed_claim("d", "Survived in original form", {}, [1672, 1679]),
                  seed_claim("e", "Survived in original form", {}, None))
    data["claims"] += [{"claim_id": "v", "subject_id": "a", "field": "construction_range", "value": [1683, 1687],
                        "source_id": "s1", "locator": "x", "review_status": "verified"},
                       {"claim_id": "x", "subject_id": "d", "field": "construction_range", "value": [1672, 1687],
                        "source_id": "s1", "locator": "x", "review_status": "disputed"},
                       listing("b", "1670 to 79, by Wren."), listing("c", "1686-95 by Wren.")]
    data["events"] = [{"event_id": "ev", "church_id": "a", "kind": "construction", "phase": "body", "earliest_year": 1683,
                       "latest_year": 1687, "claim_ids": ["v"], "date_role": "construction_interval"}]
    chosen = {row["church_id"]: row for row in choose_construction(data)}
    assert chosen["a"]["evidence_tier"] == "verified" and chosen["a"]["phase"] == "body"
    assert chosen["b"]["evidence_tier"] == "agreeing_sources"
    assert chosen["c"]["evidence_tier"] == "disputed" and chosen["c"]["alternatives"] == [[1686, 1695]]
    assert chosen["d"]["evidence_tier"] == "disputed"
    assert chosen["e"]["evidence_tier"] == "missing" and chosen["e"]["earliest_year"] is None


def test_legacy_verified_body_event_without_date_role_counts_as_interval():
    data = tables(seed_claim("a", "Survived in original form", {}, [1683, 1687]))
    data["claims"].append({"claim_id": "v", "subject_id": "a", "field": "construction_range", "value": [1683, 1687],
                           "source_id": "s1", "locator": "x", "review_status": "verified"})
    data["events"] = [{"event_id": "ev", "church_id": "a", "kind": "construction", "phase": "body",
                       "earliest_year": 1683, "latest_year": 1687, "claim_ids": ["v"]}]
    assert choose_construction(data)[0]["evidence_tier"] == "verified"


def test_verified_interval_keeps_differing_seed_range_as_alternative():
    data = tables(seed_claim("a", "Stones re-used", {}, [1670, 1674]))
    data["claims"].append({"claim_id": "v", "subject_id": "a", "field": "construction_range", "value": [1672, 1677],
                           "source_id": "s1", "locator": "x", "review_status": "verified"})
    data["events"] = [{"event_id": "ev", "church_id": "a", "kind": "construction", "phase": "body",
                       "earliest_year": 1672, "latest_year": 1677, "claim_ids": ["v"]}]
    row = choose_construction(data)[0]
    assert (row["earliest_year"], row["latest_year"], row["alternatives"]) == (1672, 1677, [[1670, 1674]])
