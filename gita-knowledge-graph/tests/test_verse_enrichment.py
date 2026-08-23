from gita_kg import parse_sanskrit, parse_transliteration, verse_text_ops

SOURCE_SAMPLE = """---
chapter: 2
verse: 47
---
## Original Sanskrit

कर्मण्येवाधिकारस्ते मा फलेषु कदाचन।

## Transliteration

karmaṇy-evādhikāras te mā phaleṣhu kadāchana

## Word Meanings

| Word | Meaning |
|---|---|
| karma | action |

## Translation

Your right is only to work.
"""


def test_parse_sanskrit_and_transliteration():
    assert "कर्मण्येवाधिकारस्ते" in parse_sanskrit(SOURCE_SAMPLE)
    assert "karmaṇy-evādhikāras" in parse_transliteration(SOURCE_SAMPLE)


def test_parse_source_text_missing_returns_empty():
    assert parse_sanskrit("## Translation\nx\n") == ""
    assert parse_transliteration("## Translation\nx\n") == ""


def test_verse_text_ops_sets_source_text():
    ops = verse_text_ops({"2.47": ("SANSKRIT", "TRANSLIT")})
    cypher, params = ops[0]
    assert "MATCH (v:Verse {id: $id})" in cypher
    assert "v.sanskrit = $sanskrit" in cypher
    assert "v.transliteration = $transliteration" in cypher
    assert params == {"id": "2.47", "sanskrit": "SANSKRIT", "transliteration": "TRANSLIT"}
