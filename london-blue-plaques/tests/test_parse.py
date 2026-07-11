"""Unit tests for parsing — run against saved fixtures, no network."""
import json
from pathlib import Path

from scrape_plaques import (
    parse_borough,
    parse_detail_html,
    parse_list_record,
    parse_name_and_dates,
    parse_plaque,
)

FIXTURES = Path(__file__).parent / "fixtures"


def _abercrombie_record() -> dict:
    plaques = json.loads((FIXTURES / "sample_list.json").read_text())["plaques"]
    return next(p for p in plaques if p["id"] == "87558")


def _detail_html() -> str:
    return (FIXTURES / "sample_detail.html").read_text()


def test_parse_name_and_dates_person():
    name, born, died = parse_name_and_dates("ABERCROMBIE, Sir Patrick (1879-1957)")
    assert name == "Sir Patrick Abercrombie"
    assert born == 1879
    assert died == 1957


def test_parse_name_and_dates_place_has_no_dates():
    name, born, died = parse_name_and_dates("14 BUCKINGHAM STREET")
    assert name == "14 BUCKINGHAM STREET"
    assert born is None and died is None


def test_parse_borough_takes_last_segment():
    addr = "Flat 1, 63 Egerton Gardens, Brompton, SW3 2BZ, London Borough of Kensington And Chelsea"
    assert parse_borough(addr) == "London Borough of Kensington And Chelsea"
    assert parse_borough(None) is None


def test_parse_list_record_core_fields():
    row = parse_list_record(_abercrombie_record())
    assert row["id"] == "87558"
    assert row["name"] == "Sir Patrick Abercrombie"
    assert row["born"] == 1879 and row["died"] == 1957
    assert row["borough"] == "London Borough of Kensington And Chelsea"
    assert row["detail_url"] == "/visit/blue-plaques/sir-patrick-abercrombie/"


def test_parse_detail_html_fields_and_coords():
    d = parse_detail_html(_detail_html())
    assert d["category"] == "Architecture and Building"
    assert d["material"] == "Ceramic"
    assert "ABERCROMBIE" in d["inscription"].upper()
    assert d["lat"] == 51.496588
    assert d["lng"] == -0.168453


def test_parse_plaque_merges_list_and_detail():
    row = parse_plaque(_abercrombie_record(), _detail_html())
    assert row["name"] == "Sir Patrick Abercrombie"
    assert row["category"] == "Architecture and Building"
    assert isinstance(row["lat"], float)
