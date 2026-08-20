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


from collections import Counter
from dataclasses import dataclass

from gita_kg import select_terms


@dataclass
class FakeTok:
    lemma_: str
    pos_: str
    is_stop: bool = False
    is_alpha: bool = True


def test_select_terms_keeps_nouns_and_verbs():
    toks = [
        FakeTok("duty", "NOUN"),
        FakeTok("perform", "VERB"),
        FakeTok("the", "DET", is_stop=True),
        FakeTok("O", "INTJ"),
        FakeTok("2", "NUM", is_alpha=False),
    ]
    assert select_terms(toks) == Counter({"duty": 1, "perform": 1})


def test_select_terms_lowercases_and_counts():
    toks = [FakeTok("Action", "NOUN"), FakeTok("action", "NOUN")]
    assert select_terms(toks) == Counter({"action": 2})


def test_select_terms_drops_stopword_verbs():
    toks = [FakeTok("be", "VERB", is_stop=True), FakeTok("act", "VERB")]
    assert select_terms(toks) == Counter({"act": 1})


import pytest


@pytest.mark.integration
def test_extract_terms_with_real_model():
    nlp = spacy.load("en_core_web_sm")
    from gita_kg import extract_terms

    doc = nlp("Your right is only to work, but not to its results.")
    terms = extract_terms(doc)
    assert "work" in terms
    assert "right" in terms
    assert "to" not in terms
