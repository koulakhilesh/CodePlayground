"""Unit tests for Gita KG parsing — run against fixtures, no Neo4j, no network."""
from pathlib import Path

from gita_kg import load_config

FIXTURES = Path(__file__).parent / "fixtures"


def test_load_config_reads_env():
    env = {
        "NEO4J_URI": "bolt://localhost:7687",
        "NEO4J_USER": "neo4j",
        "NEO4J_PASSWORD": "secret",
    }
    cfg = load_config(env)
    assert cfg.uri == "bolt://localhost:7687"
    assert cfg.user == "neo4j"
    assert cfg.password == "secret"
    assert cfg.database == "TheGitaProject"


def test_load_config_defaults_uri():
    cfg = load_config({"NEO4J_USER": "neo4j", "NEO4J_PASSWORD": "secret"})
    assert cfg.uri == "bolt://localhost:7687"
