from gita_kg import WordMeaning, parse_word_meanings
from gita_kg import is_sanskrit_stopword, normalize_sanskrit_term
from gita_kg import SanskritTermRecord, aggregate_sanskrit_terms
from gita_kg import sanskrit_term_constraint_ops, sanskrit_term_ops

WM_SAMPLE = """---
chapter: 2
verse: 47
---
## Word Meanings

| Word | Meaning |
|---|---|
| karmaṇi | in prescribed duties |
| eva | only |
| mā | not |

## Translation

Your right is only to work.
"""


def test_parse_word_meanings_extracts_surface_and_gloss():
    rows = parse_word_meanings(WM_SAMPLE)
    assert rows == [
        WordMeaning("karmaṇi", "in prescribed duties"),
        WordMeaning("eva", "only"),
        WordMeaning("mā", "not"),
    ]


def test_parse_word_meanings_missing_section_returns_empty():
    assert parse_word_meanings("## Translation\nText only.\n") == []


def test_normalize_strips_diacritics_and_lowercases():
    assert normalize_sanskrit_term("Karmaṇi") == "karma"
    assert normalize_sanskrit_term("jñānam") == "jnana"
    assert normalize_sanskrit_term("karma-phala") == "karma"


def test_stopwords_flag_particles_not_concepts():
    assert is_sanskrit_stopword("cha") is True
    assert is_sanskrit_stopword("eva") is True
    assert is_sanskrit_stopword("karma") is False
    assert is_sanskrit_stopword("jñāna") is False


def test_stopwords_exclude_epithets_and_speaker_markers():
    assert is_sanskrit_stopword("pārtha") is True          # epithet of Arjuna
    assert is_sanskrit_stopword("kaunteya") is True         # epithet of Arjuna
    assert is_sanskrit_stopword("arjunahuvacha") is True    # speaker marker (sandhi)
    assert is_sanskrit_stopword("śhrī-bhagavān uvācha") is True
    assert is_sanskrit_stopword("karma") is False           # concept survives
    assert is_sanskrit_stopword("jñāna") is False


def test_aggregate_groups_by_root_and_drops_particles():
    per_verse = {
        "2.47": [WordMeaning("karmaṇi", "in prescribed duties"),
                 WordMeaning("eva", "only")],
        "3.8": [WordMeaning("karma", "action")],
    }
    out = aggregate_sanskrit_terms(per_verse)
    assert out == [SanskritTermRecord("karma", "in prescribed duties", ("2.47", "3.8"))]


def test_constraint_is_unique_on_lemma():
    cypher, params = sanskrit_term_constraint_ops()[0]
    assert "CONSTRAINT" in cypher
    assert "SanskritTerm" in cypher
    assert "lemma" in cypher
    assert params == {}


def test_term_ops_merge_node_and_contains_edges():
    rec = SanskritTermRecord("karma", "action", ("2.47", "3.8"))
    ops = sanskrit_term_ops([rec])
    node_cypher, node_params = ops[0]
    assert "MERGE (t:SanskritTerm {lemma: $lemma})" in node_cypher
    assert node_params == {"lemma": "karma", "gloss": "action"}
    edge_cypher, edge_params = ops[1]
    assert "MERGE (v)-[:CONTAINS_TERM]->(t)" in edge_cypher
    assert edge_params == {"lemma": "karma", "verse_ids": ["2.47", "3.8"]}
