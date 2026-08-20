"""Cypher builders return (statement, params) with no driver involved."""
from gita_kg import (
    FullVerse,
    constraint_ops,
    seed_ops,
    verse_ops,
)


def test_constraint_ops_cover_all_unique_keys():
    stmts = " ".join(c for c, _ in constraint_ops())
    for key in [
        "Text", "Chapter", "Verse", "Person", "Epithet", "Place", "Term",
    ]:
        assert key in stmts
    assert all("CONSTRAINT" in c.upper() for c, _ in constraint_ops())


def test_seed_ops_are_all_merges():
    ops = seed_ops()
    assert ops, "expected seed operations"
    assert all("MERGE" in c.upper() for c, _ in ops)
    joined = " ".join(c for c, _ in ops)
    assert "EPITHET_OF" in joined
    assert "CHARIOTEER_OF" in joined
    assert "SET_IN" in joined


def _verse(id_, chapter, verse, terms=None, epithets=None):
    return FullVerse(
        chapter=chapter, verse=verse, id=id_,
        translation="x", speaker="Krishna", addressee="Arjuna",
        epithets=epithets or [], terms=terms or {},
    )


def test_verse_ops_link_next_within_chapter_only():
    records = [
        _verse("1.1", 1, 1), _verse("1.2", 1, 2), _verse("2.1", 2, 1),
    ]
    joined = " ".join(c for c, _ in verse_ops(records))
    params = [p for _, p in verse_ops(records)]
    assert ":NEXT" in joined
    next_pairs = {
        (p["from_id"], p["to_id"]) for p in params if "to_id" in p
    }
    assert ("1.1", "1.2") in next_pairs
    assert ("1.2", "2.1") not in next_pairs  # chapter boundary


def test_verse_ops_emit_term_edges_with_count():
    records = [_verse("2.47", 2, 47, terms={"work": 2, "result": 1})]
    joined = " ".join(c for c, _ in verse_ops(records))
    assert "MENTIONS_TERM" in joined
    assert "count" in joined.lower()
