"""Pure-builder tests for the C1 Theme layer. No Neo4j."""
from gita_kg import THEMES, theme_constraint_ops, theme_ops


def test_themes_have_required_shape():
    assert len(THEMES) == 13
    for name, spec in THEMES.items():
        assert isinstance(name, str) and name
        assert spec["label"] and spec["category"]
        assert isinstance(spec["lemmas"], list) and spec["lemmas"]


def test_theme_constraint_targets_name():
    ops = theme_constraint_ops()
    stmts = " ".join(c for c, _ in ops)
    assert "Theme" in stmts
    assert "CONSTRAINT" in stmts.upper()
    assert "name" in stmts
    assert all("MERGE" not in c.upper() for c, _ in ops)


_SAMPLE = {
    "karma": {"label": "Karma — Action", "category": "ethics",
              "lemmas": ["action", "duty"]},
}


def test_theme_ops_merge_theme_node_with_props():
    ops = theme_ops(_SAMPLE)
    node_ops = [(c, p) for c, p in ops if ":Theme" in c and "MERGE" in c and "INCLUDES_TERM" not in c and "MENTIONS_THEME" not in c]
    assert node_ops, "expected a Theme MERGE op"
    _, params = node_ops[0]
    assert params["name"] == "karma"
    assert params["label"] == "Karma — Action"
    assert params["category"] == "ethics"


def test_theme_ops_includes_term_edges():
    ops = theme_ops(_SAMPLE)
    joined = " ".join(c for c, _ in ops)
    assert "INCLUDES_TERM" in joined
    assert any(p.get("lemmas") == ["action", "duty"] for _, p in ops)


def test_theme_ops_weighted_mentions_from_term_counts():
    ops = theme_ops(_SAMPLE)
    joined = " ".join(c for c, _ in ops)
    assert "MENTIONS_THEME" in joined
    assert "weight" in joined.lower()
    assert "sum(m.count)" in joined


def test_theme_ops_are_all_merges():
    ops = theme_ops(_SAMPLE)
    assert all("MERGE" in c.upper() for c, _ in ops)


def test_theme_ops_defaults_to_full_taxonomy():
    ops = theme_ops()  # THEMES default
    names = {p.get("name") for _, p in ops if "name" in p}
    assert "karma" in names and "bhakti" in names
