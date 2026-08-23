from gita_kg import (
    WordMeaning,
    is_vibhuti_declaration,
    vibhuti_constraint_ops,
    vibhuti_ops,
)


def test_vibhuti_true_for_ch10_asmi_declaration():
    rows = [
        WordMeaning("ādityānām", "amongst the sons of Aditi"),
        WordMeaning("asmi", "I am"),
    ]
    assert is_vibhuti_declaration(10, rows) is True


def test_vibhuti_false_outside_ch10():
    rows = [WordMeaning("asmi", "I am")]
    assert is_vibhuti_declaration(2, rows) is False


def test_vibhuti_false_without_asmi():
    rows = [WordMeaning("aham", "I"), WordMeaning("viṣhṇuḥ", "Lord Vishnu")]
    assert is_vibhuti_declaration(10, rows) is False


def test_vibhuti_constraint_unique_on_name():
    cypher, params = vibhuti_constraint_ops()[0]
    assert "CONSTRAINT" in cypher and "Vibhuti" in cypher and "name" in cypher
    assert params == {}


def test_vibhuti_ops_merge_node_krishna_and_verse_links():
    ops = vibhuti_ops(["10.21", "10.22"])
    texts = [c for c, _ in ops]
    assert any("MERGE (vb:Vibhuti {name: 'divine-glories'})" in c for c in texts)
    assert any("MANIFESTS_AS" in c for c in texts)
    assert any("DECLARES_VIBHUTI" in c for c in texts)
    assert {"id": "10.21"} in [p for _, p in ops]
