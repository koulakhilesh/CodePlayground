"""Pure logic for the Bhagavad Gita knowledge graph.

Parsing, ontology seeds, spaCy entity/term extraction, and Cypher-operation
builders. No Neo4j driver calls live here — the notebook executes the ops.
English translation only; Sanskrit/transliteration/word-meanings are ignored.
"""
from __future__ import annotations

import re
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


@dataclass(frozen=True)
class VerseRecord:
    chapter: int
    verse: int
    id: str
    translation: str


_FRONTMATTER_RE = re.compile(r"^---\s*\n(.*?)\n---\s*\n", re.DOTALL)
_TRANSLATION_RE = re.compile(
    r"##\s*Translation\s*\n(.*?)(?:\n##\s|\n---\s*$|\Z)", re.DOTALL
)


def _frontmatter_int(body: str, key: str) -> int:
    m = re.search(rf"^{key}:\s*(\d+)\s*$", body, re.MULTILINE)
    if m is None:
        raise ValueError(f"missing frontmatter key: {key}")
    return int(m.group(1))


def parse_verse_file(text: str) -> VerseRecord:
    fm = _FRONTMATTER_RE.match(text)
    if fm is None:
        raise ValueError("no frontmatter block found")
    body = fm.group(1)
    chapter = _frontmatter_int(body, "chapter")
    verse = _frontmatter_int(body, "verse")

    tm = _TRANSLATION_RE.search(text)
    if tm is None:
        raise ValueError("no Translation section found")
    translation = tm.group(1).strip()

    return VerseRecord(
        chapter=chapter,
        verse=verse,
        id=f"{chapter}.{verse}",
        translation=translation,
    )
