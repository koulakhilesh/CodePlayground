from gita_kg import WordMeaning, PRINCIPALS, people_referenced_in_glosses
from gita_kg import speaker_from_word_meanings
from gita_kg import character_constraint_ops, character_ops


def test_people_referenced_maps_gloss_names_to_canonical():
    rows = [
        WordMeaning("pārtha", "Arjun, the son of Pritha"),
        WordMeaning("bhīma", "equal to Bheem and Arjun"),
        WordMeaning("karma", "action"),
    ]
    assert people_referenced_in_glosses(rows, PRINCIPALS) == {"Arjuna", "Bhima"}


def test_people_referenced_empty_when_no_names():
    rows = [WordMeaning("karma", "action"), WordMeaning("yoga", "union")]
    assert people_referenced_in_glosses(rows, PRINCIPALS) == set()


def test_nakula_discovered_from_short_gloss_spelling():
    # Ch.1 glosses spell him "Nakul", not "Nakula"; the stem key must still match.
    rows = [WordMeaning("nakulaḥ", "Nakul")]
    assert people_referenced_in_glosses(rows, PRINCIPALS) == {"Nakula"}


def test_drupada_and_virata_discovered_from_short_spellings():
    rows = [WordMeaning("drupadaḥ", "Drupad"), WordMeaning("virāṭaḥ", "Virat")]
    assert people_referenced_in_glosses(rows, PRINCIPALS) == {"Drupada", "Virata"}


def test_principals_canonicalize_gloss_variants():
    assert PRINCIPALS["arjun"] == "Arjuna"
    assert PRINCIPALS["bheem"] == "Bhima"
    assert PRINCIPALS["yudhishthir"] == "Yudhishthira"


def test_speaker_from_markers_uses_surface_not_gloss():
    assert speaker_from_word_meanings([WordMeaning("arjunaḥ uvācha", "Arjun said")]) == "Arjuna"
    # gloss wording varies ("Supreme Divine Personality"); surface is always bhagavān
    assert speaker_from_word_meanings(
        [WordMeaning("śhrī-bhagavān uvācha", "the Supreme Divine Personality said")]
    ) == "Krishna"
    assert speaker_from_word_meanings([WordMeaning("sañjayaḥ uvācha", "Sanjay said")]) == "Sanjaya"
    assert speaker_from_word_meanings(
        [WordMeaning("dhṛitarāśhtraḥ uvācha", "Dhritarashtra said")]
    ) == "Dhritarashtra"


def test_speaker_none_when_no_or_bare_marker():
    assert speaker_from_word_meanings([WordMeaning("karma", "action")]) is None
    assert speaker_from_word_meanings([WordMeaning("uvācha", "said")]) is None


def test_character_constraint_unique_on_name():
    cypher, params = character_constraint_ops()[0]
    assert "CONSTRAINT" in cypher
    assert "Character" in cypher
    assert "name" in cypher
    assert params == {}


def test_character_ops_labels_principals_merges_others_and_links():
    ops = character_ops({"1.4": ["Bhima"], "2.4": ["Arjuna"]}, person_names={"Arjuna"})
    texts = [c for c, _ in ops]
    # non-principal becomes a Character node
    assert any("MERGE (:Character {name: $name})" in c for c in texts)
    # principal (already a Person) gets the Character label instead of a duplicate
    assert any("MATCH (p:Person {name: $name}) SET p:Character" in c for c in texts)
    # every mention links Verse -> Character
    assert any("MERGE (v)-[:MENTIONS_CHARACTER]->(c)" in c for c in texts)
    assert {"id": "1.4", "name": "Bhima"} in [p for _, p in ops]


def test_character_ops_labels_all_persons_even_without_mentions():
    # Person is a role marker; every Person (incl. the narrator Sanjaya) is a Character.
    ops = character_ops({}, person_names={"Sanjaya", "Krishna"})
    labelled = {p["name"] for c, p in ops if "SET p:Character" in c}
    assert labelled == {"Sanjaya", "Krishna"}
