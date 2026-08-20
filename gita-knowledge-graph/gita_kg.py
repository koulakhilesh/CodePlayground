"""Pure logic for the Bhagavad Gita knowledge graph.

Parsing, ontology seeds, spaCy entity/term extraction, and Cypher-operation
builders. No Neo4j driver calls live here — the notebook executes the ops.
English translation only; Sanskrit/transliteration/word-meanings are ignored.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Mapping

DATABASE = "TheGitaProject"
DEFAULT_URI = "bolt://localhost:7687"


@dataclass(frozen=True)
class Neo4jConfig:
    uri: str
    user: str
    password: str
    database: str = DATABASE


def load_config(env: Mapping[str, str] | None = None) -> Neo4jConfig:
    import os

    env = os.environ if env is None else env
    return Neo4jConfig(
        uri=env.get("NEO4J_URI", DEFAULT_URI),
        user=env["NEO4J_USER"],
        password=env["NEO4J_PASSWORD"],
        database=env.get("NEO4J_DATABASE", DATABASE),
    )
