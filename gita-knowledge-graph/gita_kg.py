"""Pure logic for the Bhagavad Gita knowledge graph.

Parsing, ontology seeds, spaCy entity/term extraction, and Cypher-operation
builders. No Neo4j driver calls live here — the notebook executes the ops.
English translation only; Sanskrit/transliteration/word-meanings are ignored.
"""
from __future__ import annotations

import re
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

DATABASE = "neo4j"  # Community/Desktop default; named DBs require Enterprise
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
            "Krishna",
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


def build_epithet_ruler(nlp):
    """Attach an EntityRuler that tags EPITHET spans, id = owning person."""
    ruler = nlp.add_pipe("entity_ruler", config={"overwrite_ents": True})
    patterns = [
        {"label": "EPITHET", "pattern": epithet, "id": person}
        for person, epithets in EPITHETS.items()
        for epithet in epithets
    ]
    ruler.add_patterns(patterns)
    return nlp


def extract_epithets(doc) -> list[tuple[str, str]]:
    found = {
        (ent.text, ent.ent_id_)
        for ent in doc.ents
        if ent.label_ == "EPITHET"
    }
    return sorted(found)


_TERM_POS = {"NOUN", "VERB"}


def select_terms(tokens: Iterable) -> Counter:
    counts: Counter = Counter()
    for tok in tokens:
        if tok.pos_ in _TERM_POS and not tok.is_stop and tok.is_alpha:
            counts[tok.lemma_.lower()] += 1
    return counts


def extract_terms(doc) -> Counter:
    return select_terms(doc)


@dataclass(frozen=True)
class FullVerse:
    chapter: int
    verse: int
    id: str
    translation: str
    speaker: str
    addressee: str
    epithets: list[tuple[str, str]]
    terms: dict[str, int]


_VERSE_NUM_RE = re.compile(r"Chapter(\d+)Verse(\d+)", re.IGNORECASE)


def _verse_sort_key(path: Path) -> tuple[int, int]:
    m = _VERSE_NUM_RE.search(path.stem)
    if m is None:
        raise ValueError(f"cannot parse verse number from: {path.name}")
    return int(m.group(1)), int(m.group(2))


def build_records(verses_dir: Path, nlp) -> list[FullVerse]:
    paths = sorted(
        Path(verses_dir).glob("Chapter*/Chapter*Verse*.md"),
        key=_verse_sort_key,
    )
    records: list[FullVerse] = []
    previous_speaker: str | None = None
    for path in paths:
        rec = parse_verse_file(path.read_text())
        speaker = resolve_speaker(rec.translation, previous_speaker)
        previous_speaker = speaker
        doc = nlp(rec.translation)
        records.append(
            FullVerse(
                chapter=rec.chapter,
                verse=rec.verse,
                id=rec.id,
                translation=rec.translation,
                speaker=speaker,
                addressee=default_addressee(speaker),
                epithets=extract_epithets(doc),
                terms=dict(extract_terms(doc)),
            )
        )
    return records


TEXT_NAME = "Bhagavad Gita"
Op = tuple[str, dict]


def constraint_ops() -> list[Op]:
    specs = [
        ("Text", "name"), ("Chapter", "number"), ("Verse", "id"),
        ("Person", "name"), ("Epithet", "name"), ("Place", "name"),
        ("Term", "lemma"),
    ]
    return [
        (
            f"CREATE CONSTRAINT {label.lower()}_{prop} IF NOT EXISTS "
            f"FOR (n:{label}) REQUIRE n.{prop} IS UNIQUE",
            {},
        )
        for label, prop in specs
    ]


def seed_ops() -> list[Op]:
    ops: list[Op] = [
        ("MERGE (:Text {name: $name})", {"name": TEXT_NAME}),
    ]
    for p in PERSONS:
        ops.append(
            (
                "MERGE (n:Person {name: $name}) "
                "SET n.role = $role, n.aliases = $aliases",
                {"name": p["name"], "role": p["role"], "aliases": p["aliases"]},
            )
        )
    for number, cname in CHAPTER_NAMES.items():
        ops.append(
            (
                "MATCH (t:Text {name: $text}) "
                "MERGE (c:Chapter {number: $number}) "
                "SET c.name = $cname "
                "MERGE (t)-[:HAS_CHAPTER]->(c)",
                {"text": TEXT_NAME, "number": number, "cname": cname},
            )
        )
    for person, epithets in EPITHETS.items():
        for epithet in epithets:
            ops.append(
                (
                    "MATCH (p:Person {name: $person}) "
                    "MERGE (e:Epithet {name: $epithet}) "
                    "MERGE (e)-[:EPITHET_OF]->(p)",
                    {"person": person, "epithet": epithet},
                )
            )
    ops.append(
        (
            "MATCH (t:Text {name: $text}) "
            "MERGE (pl:Place {name: $place}) "
            "MERGE (t)-[:SET_IN]->(pl)",
            {"text": TEXT_NAME, "place": PLACE},
        )
    )
    for src, rel, dst in CAST_EDGES:
        ops.append(
            (
                f"MATCH (a:Person {{name: $src}}), (b:Person {{name: $dst}}) "
                f"MERGE (a)-[:{rel}]->(b)",
                {"src": src, "dst": dst},
            )
        )
    return ops


def verse_ops(records: list[FullVerse]) -> list[Op]:
    ops: list[Op] = []
    for r in records:
        ops.append(
            (
                "MATCH (c:Chapter {number: $chapter}) "
                "MERGE (v:Verse {id: $id}) "
                "SET v.chapter = $chapter, v.verse = $verse, "
                "v.translation = $translation "
                "MERGE (c)-[:HAS_VERSE]->(v)",
                {
                    "chapter": r.chapter, "verse": r.verse, "id": r.id,
                    "translation": r.translation,
                },
            )
        )
        ops.append(
            (
                "MATCH (v:Verse {id: $id}), (p:Person {name: $speaker}) "
                "MERGE (v)-[:SPOKEN_BY]->(p)",
                {"id": r.id, "speaker": r.speaker},
            )
        )
        ops.append(
            (
                "MATCH (v:Verse {id: $id}), (p:Person {name: $addressee}) "
                "MERGE (v)-[:ADDRESSED_TO]->(p)",
                {"id": r.id, "addressee": r.addressee},
            )
        )
        for epithet, _person in r.epithets:
            ops.append(
                (
                    "MATCH (v:Verse {id: $id}), (e:Epithet {name: $epithet}) "
                    "MERGE (v)-[:USES_EPITHET]->(e)",
                    {"id": r.id, "epithet": epithet},
                )
            )
        for lemma, count in r.terms.items():
            ops.append(
                (
                    "MATCH (v:Verse {id: $id}) "
                    "MERGE (t:Term {lemma: $lemma}) "
                    "MERGE (v)-[m:MENTIONS_TERM]->(t) "
                    "SET m.count = $count",
                    {"id": r.id, "lemma": lemma, "count": count},
                )
            )
    ops.extend(_next_ops(records))
    return ops


def _next_ops(records: list[FullVerse]) -> list[Op]:
    ops: list[Op] = []
    for a, b in zip(records, records[1:]):
        if a.chapter == b.chapter:
            ops.append(
                (
                    "MATCH (x:Verse {id: $from_id}), (y:Verse {id: $to_id}) "
                    "MERGE (x)-[:NEXT]->(y)",
                    {"from_id": a.id, "to_id": b.id},
                )
            )
    return ops


THEMES: dict[str, dict] = {
    "jnana": {"label": "Jnana — Knowledge", "category": "metaphysics",
              "lemmas": ["knowledge", "wisdom", "understanding", "know", "learn"]},
    "samsara": {"label": "Samsara — Birth & Death", "category": "metaphysics",
                "lemmas": ["birth", "death", "body", "world"]},
    "karma": {"label": "Karma — Action", "category": "ethics",
              "lemmas": ["action", "work", "deed", "fruit", "result", "act", "duty"]},
    "senses-mind": {"label": "Senses & Mind", "category": "psychology",
                    "lemmas": ["sense", "mind", "anger", "control", "intellect", "thought"]},
    "detachment": {"label": "Detachment", "category": "ethics",
                   "lemmas": ["attachment", "desire", "renunciation", "abandon", "renounce"]},
    "atman": {"label": "Atman — The Self", "category": "metaphysics",
              "lemmas": ["self", "soul", "being"]},
    "guna": {"label": "Gunas — Qualities of Nature", "category": "metaphysics",
             "lemmas": ["quality", "nature", "ignorance", "passion", "goodness", "mode"]},
    "bhakti": {"label": "Bhakti — Devotion", "category": "devotion",
               "lemmas": ["devotion", "worship", "faith", "devotee", "love", "god"]},
    "sacrifice-austerity": {"label": "Sacrifice & Austerity", "category": "ritual",
                            "lemmas": ["sacrifice", "austerity"]},
    "yoga": {"label": "Yoga — Discipline & Union", "category": "path",
             "lemmas": ["yoga", "union", "meditation", "practice", "path"]},
    "dharma": {"label": "Dharma — Duty & Righteousness", "category": "ethics",
               "lemmas": ["duty", "righteousness", "law", "sin"]},
    "moksha": {"label": "Moksha — Liberation", "category": "metaphysics",
               "lemmas": ["liberation", "freedom"]},
    "brahman": {"label": "Brahman — The Absolute", "category": "metaphysics",
                "lemmas": ["imperishable", "absolute", "brahman"]},
}


def theme_constraint_ops() -> list[Op]:
    return [
        (
            "CREATE CONSTRAINT theme_name IF NOT EXISTS "
            "FOR (n:Theme) REQUIRE n.name IS UNIQUE",
            {},
        )
    ]

