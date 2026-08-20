"""Tests for spaCy entity/term extraction. EntityRuler tests use a blank pipe."""
import spacy

from gita_kg import build_epithet_ruler, extract_epithets


def _blank_with_ruler():
    nlp = spacy.blank("en")
    return build_epithet_ruler(nlp)


def test_extract_epithets_finds_arjuna_vocative():
    nlp = _blank_with_ruler()
    doc = nlp("Perform your duty equipoised, O Partha, abandoning attachment.")
    assert ("Partha", "Arjuna") in extract_epithets(doc)


def test_extract_epithets_maps_to_krishna():
    nlp = _blank_with_ruler()
    doc = nlp("O Madhusudana, how can I fight in battle?")
    assert ("Madhusudana", "Krishna") in extract_epithets(doc)


def test_extract_epithets_empty_when_none_present():
    nlp = _blank_with_ruler()
    doc = nlp("Your right is only to work, but not to its results.")
    assert extract_epithets(doc) == []
