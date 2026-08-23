from gita_kg import (
    WordMeaning,
    conch_names_in_gloss,
    conches_in_glosses,
    CONCH_OWNERS,
    conch_constraint_ops,
    conch_ops,
)


def test_conch_name_extracted_from_gloss():
    assert conch_names_in_gloss("the conch named Anantavijay") == ["Anantavijaya"]
    assert conch_names_in_gloss("the conch shell named Panchajanya") == ["Panchajanya"]


def test_conch_pair_and_variant_spellings_normalize():
    assert conch_names_in_gloss(
        "the conche shells named Sughosh and Manipushpak"
    ) == ["Sughosha", "Manipushpa"]
    assert conch_names_in_gloss("the conch shell named Devadutta") == ["Devadatta"]


def test_non_conch_or_unnamed_gloss_yields_nothing():
    assert conch_names_in_gloss("mighty conch") == []
    assert conch_names_in_gloss("Arjun, the son of Pritha") == []


def test_conches_in_glosses_dedupes():
    rows = [
        WordMeaning("pauṇḍram", "the conch named Paundra"),
        WordMeaning("mahā-śhaṅkham", "mighty conch"),
    ]
    assert conches_in_glosses(rows) == {"Paundra"}


def test_conch_owners_are_verse_attested():
    assert CONCH_OWNERS["Panchajanya"] == "Krishna"
    assert CONCH_OWNERS["Devadatta"] == "Arjuna"
    assert CONCH_OWNERS["Anantavijaya"] == "Yudhishthira"


def test_conch_constraint_unique_on_name():
    cypher, params = conch_constraint_ops()[0]
    assert "CONSTRAINT" in cypher and "Conch" in cypher and "name" in cypher
    assert params == {}


def test_conch_ops_merge_node_owner_and_verse_link():
    ops = conch_ops({"1.15": ["Panchajanya"]})
    texts = [c for c, _ in ops]
    assert any("MERGE (c:Conch {name: $name})" in c for c in texts)
    assert any("SOUNDS_CONCH" in c for c in texts)
    assert any("NAMES_CONCH" in c for c in texts)
    assert {"id": "1.15", "name": "Panchajanya"} in [p for _, p in ops]
