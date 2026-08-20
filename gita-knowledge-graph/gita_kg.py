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


PERSONS: list[dict] = [
    {"name": "Dhritarashtra", "role": "king", "aliases": ["Dhritarashtra"]},
    {"name": "Sanjaya", "role": "narrator", "aliases": ["Sanjaya"]},
    {"name": "Arjuna", "role": "student", "aliases": ["Arjuna"]},
    {
        "name": "Krishna",
        "role": "teacher",
        "aliases": [
            "The Blessed Lord",
            "Sri Krishna",
            "The Supreme Lord",
            "Lord Krishna",
            "The Lord",
        ],
    },
]

CHAPTER_NAMES: dict[int, str] = {
    1: "Arjuna Vishada Yoga",
    2: "Sankhya Yoga",
    3: "Karma Yoga",
    4: "Jnana Karma Sanyasa Yoga",
    5: "Karma Sanyasa Yoga",
    6: "Dhyana Yoga",
    7: "Jnana Vijnana Yoga",
    8: "Akshara Brahma Yoga",
    9: "Raja Vidya Raja Guhya Yoga",
    10: "Vibhuti Yoga",
    11: "Vishwarupa Darshana Yoga",
    12: "Bhakti Yoga",
    13: "Kshetra Kshetrajna Vibhaga Yoga",
    14: "Gunatraya Vibhaga Yoga",
    15: "Purushottama Yoga",
    16: "Daivasura Sampad Vibhaga Yoga",
    17: "Shraddhatraya Vibhaga Yoga",
    18: "Moksha Sanyasa Yoga",
}

EPITHETS: dict[str, list[str]] = {
    "Arjuna": [
        "Partha", "Bharata", "Bharatarshabha", "Dhananjaya", "Gudakesha",
        "Kaunteya", "Pandava", "Parantapa", "Mahabaho", "Anagha", "Kurunandana",
    ],
    "Krishna": [
        "Kesava", "Madhava", "Govinda", "Hrishikesha", "Madhusudana",
        "Janardana", "Achyuta", "Varshneya", "Vasudeva", "Yadava", "Purushottama",
    ],
}

PLACE = "Kurukshetra"

CAST_EDGES: list[tuple[str, str, str]] = [
    ("Krishna", "CHARIOTEER_OF", "Arjuna"),
    ("Sanjaya", "NARRATES_TO", "Dhritarashtra"),
]

# alias (lowercased) -> canonical person name, longest-first for greedy match
_ALIAS_TO_PERSON: list[tuple[str, str]] = sorted(
    ((alias.lower(), p["name"]) for p in PERSONS for alias in p["aliases"]),
    key=lambda pair: len(pair[0]),
    reverse=True,
)

_ADDRESSEE = {
    "Krishna": "Arjuna",
    "Arjuna": "Krishna",
    "Sanjaya": "Dhritarashtra",
    "Dhritarashtra": "Sanjaya",
}


def resolve_speaker(translation: str, previous: str | None) -> str:
    head = translation.lstrip().lower()
    for alias, name in _ALIAS_TO_PERSON:
        if head.startswith(f"{alias} said"):
            return name
    if previous is None:
        raise ValueError("no speaker prefix and no previous speaker to inherit")
    return previous


def default_addressee(speaker: str) -> str:
    return _ADDRESSEE[speaker]
