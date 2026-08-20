"""Unit tests for Gita KG parsing — run against fixtures, no Neo4j, no network."""
from pathlib import Path

import pytest

from gita_kg import load_config, parse_verse_file

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_config_reads_env():
    env = {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "secret",
    }
    cfg = load_config(env)
    assert cfg.uri == "bolt://localhost:7687"
    assert cfg.user == "neo4j"
    assert cfg.password == "secret"
    assert cfg.database == "neo4j"


def test_load_config_defaults_uri():
    cfg = load_config({"NEO4J_USER": "neo4j", "NEO4J_PASSWORD": "secret"})
    assert cfg.uri == "bolt://localhost:7687"


def test_parse_verse_file_extracts_numbers_and_id():
    text = (FIXTURES / "verse_2_47.md").read_text()
    rec = parse_verse_file(text)
    assert rec.chapter == 2
    assert rec.verse == 47
    assert rec.id == "2.47"


def test_parse_verse_file_extracts_only_translation():
    text = (FIXTURES / "verse_2_47.md").read_text()
    rec = parse_verse_file(text)
    assert rec.translation.startswith("Your right is only to work")
    assert "karma" not in rec.translation  # word-meanings section excluded
    assert "##" not in rec.translation


from gita_kg import (
    CHAPTER_NAMES,
    PERSONS,
    default_addressee,
    resolve_speaker,
)


def test_persons_are_the_closed_cast():
    names = {p["name"] for p in PERSONS}
    assert names == {"Dhritarashtra", "Sanjaya", "Arjuna", "Krishna"}


def test_chapter_names_cover_all_eighteen():
    assert set(CHAPTER_NAMES) == set(range(1, 19))


def test_resolve_speaker_from_prefix():
    assert resolve_speaker('Dhritarashtra said, "..."', None) == "Dhritarashtra"
    assert resolve_speaker("Arjuna said, ...", "Dhritarashtra") == "Arjuna"


def test_resolve_speaker_krishna_alias():
    assert resolve_speaker("The Blessed Lord said, ...", "Arjuna") == "Krishna"


def test_resolve_speaker_inherits_when_no_prefix():
    text = (FIXTURES / "verse_no_prefix.md").read_text()
    from gita_kg import parse_verse_file

    rec = parse_verse_file(text)
    assert resolve_speaker(rec.translation, "Krishna") == "Krishna"


def test_default_addressee_pairs():
    assert default_addressee("Krishna") == "Arjuna"
    assert default_addressee("Arjuna") == "Krishna"
    assert default_addressee("Sanjaya") == "Dhritarashtra"
    assert default_addressee("Dhritarashtra") == "Sanjaya"


import spacy

from gita_kg import build_epithet_ruler, build_records, default_addressee

MINI_VAULT = FIXTURES / "mini_vault"


def _nlp():
    return build_epithet_ruler(spacy.load("en_core_web_sm"))


@pytest.mark.integration
def test_build_records_orders_and_threads_speaker():
    records = build_records(MINI_VAULT, _nlp())
    ids = [r.id for r in records]
    assert ids == ["1.1", "2.47", "2.48", "8.14"]
    by_id = {r.id: r for r in records}
    assert by_id["1.1"].speaker == "Dhritarashtra"
    # 2.48 has no "X said" prefix; inherits the last resolved speaker from 2.47.
    assert by_id["2.48"].speaker == by_id["2.47"].speaker


@pytest.mark.integration
def test_build_records_attaches_addressee_epithets_terms():
    by_id = {r.id: r for r in build_records(MINI_VAULT, _nlp())}
    v = by_id["8.14"]  # real verse containing the epithet "O Partha"
    assert ("Partha", "Arjuna") in v.epithets
    assert v.addressee == default_addressee(v.speaker)
    assert v.terms  # non-empty lemmatized term map
