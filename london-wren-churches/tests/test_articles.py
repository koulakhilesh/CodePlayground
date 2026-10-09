from pathlib import Path

from collect_wren import extract_article


def test_article_preserves_phase_cost_and_relocation_evidence():
    html = (Path(__file__).parent / "fixtures/article.html").read_text()
    tables = extract_article(html, "c1", "s1")
    claims = tables["claims"]
    passages = [claim for claim in claims if claim["field"] == "history_passage"]
    assert len(passages) == 3
    assert "7,692" in passages[0]["value"]["text"]
    assert "tower" in passages[1]["value"]["text"]
    assert "moved" in passages[2]["value"]["text"]
    assert all(claim["review_status"] == "extracted" for claim in claims)
    assert all(claim["source_id"] == "s1" and claim["locator"] for claim in claims)
    assert len({claim["claim_id"] for claim in claims}) == len(claims)
    coordinates = next(claim for claim in claims if claim["field"] == "article_coordinates")
    assert coordinates["value"] == [51.5, -0.1]
    assert tables["places"] == []
    assert tables["events"] == []


def test_conflicting_prose_dates_are_not_resolved_automatically():
    tables = extract_article("<h2>History</h2><p>Completed in 1679.</p><p>Another account gives 1687.</p>", "c1", "s1")
    assert [claim["value"]["text"] for claim in tables["claims"]] == [
        "Completed in 1679.", "Another account gives 1687."]
    assert tables["events"] == []


def test_article_without_infobox_retains_history():
    tables = extract_article("<h2>History</h2><p>Gutted by fire.</p>", "c1", "s1")
    assert tables["claims"][0]["value"]["text"] == "Gutted by fire."
    assert tables["places"] == []


def test_official_links_are_candidates_not_verified_sources():
    html = (Path(__file__).parent / "fixtures/article.html").read_text()
    tables = extract_article(html, "c1", "s1")
    links = tables["source_targets"]
    assert {link["url"] for link in links} == {
        "https://historicengland.org.uk/listing/the-list/list-entry/123",
        "https://example.org/church"}
    assert all(link["subject_id"] == "c1" for link in links)


def test_navigation_paragraphs_are_not_article_history():
    html = '<p>Navigation text</p><div id="mw-content-text"><h2>History</h2><p>Real evidence.</p></div>'
    tables = extract_article(html, "c1", "s1")
    assert len(tables["claims"]) == 1
    assert tables["claims"][0]["value"]["text"] == "Real evidence."