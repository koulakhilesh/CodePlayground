from context_wren import link_parishes, parse_not_rebuilt

HTML = """
<table class="wikitable"><tr><th>Church name</th><th>Location</th><th>United with</th></tr>
<tr><td><a href="/wiki/St_Benet_Sherehog">St Benet Sherehog</a></td><td>Poultry [ 3 ]</td>
<td><a href="/wiki/St_Stephen_Walbrook">St Stephen Walbrook</a></td></tr>
<tr><td><a href="/wiki/St_Thomas_the_Apostle">St Thomas the Apostle</a></td><td>St Thomas Apostle Street</td>
<td><a href="/w/index.php?title=St_Mary_Aldermary,_Watling_Street&amp;action=edit&amp;redlink=1">St Mary Aldermary, Watling Street</a></td></tr>
<tr><td>St Mary Woolchurch Haw</td><td>Queen Victoria Street</td><td><a href="/wiki/St_Mary_Woolnoth">St Mary Woolnoth</a> (ibid)</td></tr>
</table>
"""
CHURCHES = [{"church_id": "walbrook", "name": "St Stephen Walbrook", "article_url": "https://en.wikipedia.org/wiki/St_Stephen_Walbrook"},
            {"church_id": "aldermary", "name": "St Mary Aldermary", "article_url": "https://en.wikipedia.org/wiki/St_Mary_Aldermary"}]
SOURCE = {"source_id": "s", "url": "https://en.wikipedia.org/wiki/List"}


def test_parse_keeps_text_and_drops_red_links_and_footnotes():
    rows = parse_not_rebuilt(HTML)
    assert [row["name"] for row in rows] == ["St Benet Sherehog", "St Thomas the Apostle", "St Mary Woolchurch Haw"]
    assert rows[0]["location"] == "Poultry"
    assert rows[1]["united_with_url"] is None
    assert rows[2]["united_with"] == "St Mary Woolnoth" and rows[2]["article_url"] is None


def test_link_uses_url_then_review_override_and_keeps_non_candidates_unmatched():
    overrides = {"St Mary Aldermary, Watling Street": {"church_id": "aldermary"}}
    tables, unmatched = link_parishes(parse_not_rebuilt(HTML), CHURCHES, SOURCE, overrides)
    methods = {row["name"]: (row["united_church_id"], row["match_method"]) for row in tables["parishes"]}
    assert methods["St Benet Sherehog"] == ("walbrook", "article_url")
    assert methods["St Thomas the Apostle"] == ("aldermary", "review_override")
    assert methods["St Mary Woolchurch Haw"] == (None, None)
    assert [row["united_with"] for row in unmatched] == ["St Mary Woolnoth"]
    assert {event["kind"] for event in tables["events"]} == {"parish_merger"}
    assert all(event["evidence_tier"] == "reported" and event["earliest_year"] is None for event in tables["events"])


def test_population_flags_non_census_years_and_estimates():
    from context_wren import parse_population
    html = """<table><tr><th>Year</th><th>Pop.</th><th>±%</th></tr>
    <tr><th>1931</th><td>15,758</td><td>-19.5%</td></tr><tr><th>1941</th><td>10,920</td><td>-30.7%</td></tr>
    <tr><th>2024 estimate</th><td>15,111</td><td>+75.7%</td></tr><tr><td colspan="3">Sources: ONS</td></tr></table>"""
    rows = parse_population(html, "s")
    assert [(row["year"], row["population"], row["count_type"]) for row in rows] == [
        (1931, 15758, "census"), (1941, 10920, "not_census"), (2024, 15111, "estimate")]
    assert rows[1]["caveat"]


def test_related_site_links_lost_parish_and_keeps_caveat():
    from context_wren import parse_related_site
    html = """<div id="mw-content-text"><span class="geo">51.51014; -0.08594</span>
    <p>Constructed between 1671 and 1677, it was built on the site of St Margaret, New Fish Street.</p>
    <p>Unrelated paragraph.</p><p>Christopher Wren was asked to submit a design.</p></div>"""
    site = {"name": "Monument", "url": "https://example.org/m", "keywords": ("Wren", "Constructed between"),
            "on_site_of_parish": "St Margaret, New Fish Street", "caveat": "Hooke design."}
    parsed = parse_related_site(html, site, "s", [{"parish_id": "p1", "name": "St Margaret, New Fish Street"}])
    row = parsed["related_sites"][0]
    assert (row["latitude"], row["longitude"], row["on_site_of_parish_id"]) == (51.51014, -0.08594, "p1")
    assert [claim["locator"] for claim in parsed["claims"]] == ["p[1]", "p[3]"]
    assert row["caveat"] == "Hooke design." and row["evidence_tier"] == "reported"


def test_parentalia_quotes_are_checked_against_ocr_text():
    import pytest
    from context_wren import parentalia_claims
    ocr = "A Catalogue  of Fifty-\none parochial Churches ... XL. St. Michael Royal Church was rebuilt in 1694. The Walls"
    review = {"reviewed_at": "2026-10-08", "heading_quote": "A Catalogue of Fifty- one parochial Churches",
              "entries": [{"number": "XL", "name": "St Michael Royal", "church_id": "c", "quote": "was rebuilt in 1694", "year": 1694},
                          {"number": "L", "name": "St Sepulchre's", "church_id": None}]}
    claims = parentalia_claims(review, ocr, "s", {"c"})["claims"]
    assert [(claim["subject_id"], claim["value"]["year"]) for claim in claims] == [("c", 1694)]
    review["entries"][0]["quote"] = "was rebuilt in 1695"
    with pytest.raises(ValueError):
        parentalia_claims(review, ocr, "s", {"c"})
