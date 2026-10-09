from visitors_wren import build_listings, listing_scope, parse_listing_page, published_status


def page(opening: str | None) -> str:
    block = (f'<div class="church-info-item"><div class="church-info-title">Usual opening times</div>'
             f'<div class="church-info-text">{opening}</div></div>') if opening else ""
    return (f'<main>{block}<div class="church-info-item"><div class="church-info-title">Location</div>'
            '<div class="church-info-text">Walbrook, EC4N</div></div></main>')


def test_scope_comes_from_listing_title():
    assert listing_scope("St Mary Somerset (Tower Only)") == ("St Mary Somerset", "tower")
    assert listing_scope("St Dunstan in the East (Tower and Gardens only)") == ("St Dunstan in the East", "tower_and_garden")
    assert listing_scope("St Mary Aldermanbury (Gardens and remains only)") == ("St Mary Aldermanbury", "garden_and_remains")
    assert listing_scope("St Stephen Walbrook") == ("St Stephen Walbrook", "interior")


def test_published_status_distinguishes_closure_from_service_restrictions():
    assert published_status("The church will be closed for period from August 2026 for refurbishment works") == "closure_notice"
    assert published_status("Currently not open to the public") == "closure_notice"
    assert published_status("Monday to Friday 7am to 4.30pm although there is a service each Thursday") == "hours_published"
    assert published_status("By arrangement only") == "by_arrangement"
    assert published_status("No regular opening times at present") == "no_regular_hours"
    assert published_status(None) == "no_hours_listed"


def test_listing_keeps_text_and_flags_fee_without_parsing_hours():
    parsed = parse_listing_page(page("Monday to Friday 10am to 4pm (N.B. an entrance fee is charged)"))
    assert parsed["opening_text"].startswith("Monday to Friday")
    assert parsed["fee_mentioned"] and not parsed["closure_notice"]
    assert "opens" not in parsed and "open_now" not in parsed


def test_build_listings_routes_garden_sites_to_lost_parishes():
    index = [{"link": "https://x/church/a/", "title": {"rendered": "St Stephen Walbrook"}},
             {"link": "https://x/church/b/", "title": {"rendered": "St Pancras Soper Lane (Garden Only)"}},
             {"link": "https://x/church/c/", "title": {"rendered": "Bevis Marks Synagogue"}}]
    source = {"source_id": "s", "retrieved_at": "2026-10-08T00:00:00+00:00"}
    pages = {"https://x/church/a/": (source, page("Monday-Friday: 10.30am to 3.30pm")),
             "https://x/church/b/": (source, page(None))}
    churches = [{"church_id": "walbrook", "name": "St Stephen Walbrook"}]
    parishes = [{"parish_id": "pancras", "name": "St Pancras, Soper Lane"}]
    tables, unmatched = build_listings(index, pages, churches, {}, parishes)
    rows = {row["title"]: row for row in tables["visitor_listings"]}
    assert rows["St Stephen Walbrook"]["church_id"] == "walbrook"
    assert rows["St Pancras Soper Lane (Garden Only)"]["parish_id"] == "pancras"
    assert rows["St Pancras Soper Lane (Garden Only)"]["church_id"] is None
    assert unmatched == ["Bevis Marks Synagogue"]
    assert all(row["checked_at"] == "2026-10-08" and row["evidence_tier"] == "third_party_published"
               for row in rows.values())


def test_official_quotes_must_appear_in_cached_page():
    import pytest
    from visitors_wren import official_listings
    tables = {"sources": [{"source_id": "s", "url": "https://x/visit", "retrieved_at": "2026-10-08T00:00:00+00:00"}],
              "claims": [{"claim_id": "c", "subject_id": "a", "source_id": "s", "field": "visitor_source_passage",
                          "value": {"text": "We\u2019re open  from 8.30am Monday to Saturday."}}]}
    page = {"church_id": "a", "url": "https://x/visit", "publisher": "P", "access_scope": "interior",
            "published_status": "hours_published", "opening_quotes": ["We're open from 8.30am Monday to Saturday."]}
    rows = official_listings({"reviewed_at": "2026-10-08", "pages": [page]}, tables)["visitor_listings"]
    assert rows[0]["evidence_tier"] == "official_published" and rows[0]["checked_at"] == "2026-10-08"
    page["opening_quotes"] = ["Open every day"]
    with pytest.raises(ValueError):
        official_listings({"reviewed_at": "2026-10-08", "pages": [page]}, tables)
