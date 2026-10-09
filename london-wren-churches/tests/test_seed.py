from pathlib import Path

import pytest

from collect_wren import parse_coordinates, parse_seed, parse_year_range


def test_seed_keeps_duplicate_candidates_and_variable_columns():
    html = (Path(__file__).parent / "fixtures/seed.html").read_text()
    rows = parse_seed(html, "s1", "https://en.wikipedia.org")
    assert len(rows) == 4
    assert rows[0]["article_url"] == "https://en.wikipedia.org/wiki/Test_Church"
    assert rows[0]["date_range"] == [1677, 1683]
    assert rows[0]["coordinates"] == [51.5, -0.1]
    assert rows[1]["coordinates"] is None
    assert rows[2]["article_url"] == rows[0]["article_url"]
    assert rows[2]["section"] == "Tower remaining"
    assert rows[3]["section"] == "Churches built outside the City of London"
    assert len({row["seed_id"] for row in rows}) == 4
    assert all(row["source_id"] == "s1" and row["locator"] for row in rows)


@pytest.mark.parametrize("text,expected", [
    ("1677–83", [1677, 1683]), ("1698–02", [1698, 1702]),
    ("1675-1711", [1675, 1711]), ("1680", [1680, 1680]),
    ("unknown", None), ("c. 1680", None), ("1670, 1710", None),
])
def test_year_ranges_do_not_invent_precision(text, expected):
    assert parse_year_range(text) == expected


@pytest.mark.parametrize("text,expected", [
    ("51°30′0″N 0°6′0″W", [51.5, -0.1]),
    ("51.5; -0.1", [51.5, -0.1]),
    ("unknown", None), ("95; -0.1", None),
])
def test_coordinate_formats(text, expected):
    assert parse_coordinates(text) == expected


def test_seed_rejects_empty_extraction():
    with pytest.raises(ValueError, match="seed rows"):
        parse_seed("<html>Consent page</html>", "s1", "https://en.wikipedia.org")


@pytest.mark.parametrize("href", ["https://en.wikipedia.org/wiki/Test_Church", "./Test_Church"])
def test_seed_supports_live_absolute_and_parsoid_links(href):
    html = f'<h3>Tower remaining</h3><table class="wikitable"><tr><th>Name</th></tr><tr><td><a href="{href}">Test Church</a></td></tr></table>'
    rows = parse_seed(html, "s1", "https://en.wikipedia.org/wiki/List_of_Churches")
    assert rows[0]["article_url"] == "https://en.wikipedia.org/wiki/Test_Church"