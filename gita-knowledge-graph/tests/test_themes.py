"""Pure-builder tests for the C1 Theme layer. No Neo4j."""
from gita_kg import THEMES, theme_constraint_ops


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
