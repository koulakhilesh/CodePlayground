from gita_kg import CONCEPTS, concept_constraint_ops, concept_ops
from gita_kg import THEMES, concept_theme_alignment_ops


def test_concepts_have_label_category_prefixes():
    for name, spec in CONCEPTS.items():
        assert spec["label"] and spec["category"] and spec["prefixes"]


def test_concept_constraint_unique_on_name():
    cypher, params = concept_constraint_ops()[0]
    assert "CONSTRAINT" in cypher
    assert "Concept" in cypher
    assert "name" in cypher
    assert params == {}


def test_concept_ops_merge_node_instance_and_expresses():
    concepts = {
        "atman": {
            "label": "Ātman — the Self",
            "category": "metaphysics",
            "prefixes": ["atman", "atma"],
        }
    }
    ops = concept_ops(concepts)
    node_c, node_p = ops[0]
    assert "MERGE (c:Concept {name: $name})" in node_c
    assert node_p == {
        "name": "atman",
        "label": "Ātman — the Self",
        "category": "metaphysics",
    }

    inst_c, inst_p = ops[1]
    assert "INSTANCE_OF" in inst_c
    assert "SanskritTerm" in inst_c
    assert inst_p == {"name": "atman", "prefixes": ["atman", "atma"]}

    expr_c, expr_p = ops[2]
    assert "EXPRESSES_CONCEPT" in expr_c
    assert "CONTAINS_TERM" in expr_c
    assert expr_p == {"name": "atman", "prefixes": ["atman", "atma"]}


def test_concept_theme_alignment_links_only_shared_names():
    ops = concept_theme_alignment_ops()
    names = {p["name"] for _, p in ops}
    assert names == set(CONCEPTS) & set(THEMES)
    assert all("ALIGNS_WITH" in c for c, _ in ops)
    assert "karma" in names and "dharma" in names   # shared
    assert "buddhi" not in names                      # concept-only
    assert "detachment" not in names                  # theme-only
