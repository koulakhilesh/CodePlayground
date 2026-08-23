"""Pure logic for the Bhagavad Gita knowledge graph.

Parsing, ontology seeds, spaCy entity/term extraction, and Cypher-operation
builders. No Neo4j driver calls live here — the notebook executes the ops.
Reads the English translation plus the Sanskrit, transliteration, and
word-by-word Word Meanings layers.
"""
from __future__ import annotations

import re
import unicodedata
from collections import Counter
from dataclasses import dataclass
from pathlib import Path
from typing import Iterable, Mapping

import numpy as np

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


_WORD_MEANINGS_RE = re.compile(
    r"##\s*Word Meanings\s*\n(.*?)(?:\n##\s|\n---\s*$|\Z)", re.DOTALL
)
_WM_ROW_RE = re.compile(r"^\|\s*(.+?)\s*\|\s*(.+?)\s*\|\s*$")


@dataclass(frozen=True)
class WordMeaning:
    surface: str
    gloss: str


def parse_word_meanings(text: str) -> list[WordMeaning]:
    m = _WORD_MEANINGS_RE.search(text)
    if m is None:
        return []
    rows: list[WordMeaning] = []
    for line in m.group(1).splitlines():
        rm = _WM_ROW_RE.match(line.strip())
        if rm is None:
            continue
        surface, gloss = rm.group(1).strip(), rm.group(2).strip()
        if surface.lower() == "word" or set(surface) <= {"-", ":"}:
            continue
        rows.append(WordMeaning(surface, gloss))
    return rows


_SANSKRIT_RE = re.compile(
    r"##\s*Original Sanskrit\s*\n(.*?)(?:\n##\s|\n---\s*$|\Z)", re.DOTALL
)
_TRANSLITERATION_RE = re.compile(
    r"##\s*Transliteration\s*\n(.*?)(?:\n##\s|\n---\s*$|\Z)", re.DOTALL
)


def parse_sanskrit(text: str) -> str:
    m = _SANSKRIT_RE.search(text)
    return m.group(1).strip() if m else ""


def parse_transliteration(text: str) -> str:
    m = _TRANSLITERATION_RE.search(text)
    return m.group(1).strip() if m else ""


SANSKRIT_STOPLIST: frozenset[str] = frozenset({
    # pronouns / particles / conjunctions
    "cha", "na", "eva", "hi", "tu", "api", "iti", "aham", "tat", "sah",
    "yah", "yat", "me", "te", "tvam", "mam", "maya", "idam", "etat", "ye",
    "kim", "asmi", "tatha", "saha", "va", "ha", "u", "atha", "asti",
    "evam", "tatah", "tam", "tasmat", "mama", "mat", "tan", "esah", "esa",
    "ayam", "ena", "yena", "tena", "yasya", "tasya", "yada", "sada", "ca",
    # grammatical verbs / adjectival function words seen as noise
    "viddhi", "uchyate", "bhavati", "asau", "iva", "cha-api",
    "sarva", "maha", "param", "shri", "uvacha",
})

SANSKRIT_ROOT_ALIASES: dict[str, str] = {
    "karmani": "karma", "karma-phala": "karma", "karmana": "karma",
    "jnanam": "jnana", "jnanena": "jnana",
    "yogah": "yoga", "yogam": "yoga", "yogena": "yoga",
    "atma": "atman", "atmanam": "atman",
    "manah": "manas", "manasa": "manas",
}


def _strip_diacritics(s: str) -> str:
    decomposed = unicodedata.normalize("NFKD", s)
    ascii_str = "".join(c for c in decomposed if not unicodedata.combining(c))
    return ascii_str.replace("ṁ", "m").replace("ḥ", "h")


def _clean_sanskrit_key(surface: str) -> str:
    key = _strip_diacritics(surface).lower().strip()
    return re.sub(r"[^a-z-]", "", key).strip("-")


def normalize_sanskrit_term(surface: str) -> str:
    key = _clean_sanskrit_key(surface)
    if key in SANSKRIT_ROOT_ALIASES:
        return SANSKRIT_ROOT_ALIASES[key]
    head = key.split("-", 1)[0]
    return SANSKRIT_ROOT_ALIASES.get(head, head or key)


def is_sanskrit_stopword(surface: str) -> bool:
    full = _clean_sanskrit_key(surface)
    if not full:
        return True
    if "uvacha" in full:  # speaker attribution, incl. sandhi (arjuna uvacha)
        return True
    lemma = normalize_sanskrit_term(surface)
    return lemma in SANSKRIT_STOPLIST or lemma in _EPITHET_STOPSET


def _verse_id_sort_key(vid: str) -> tuple[int, int]:
    c, v = vid.split(".")
    return int(c), int(v)


@dataclass(frozen=True)
class SanskritTermRecord:
    lemma: str
    gloss: str
    verse_ids: tuple[str, ...]


def aggregate_sanskrit_terms(
    per_verse: Mapping[str, list[WordMeaning]],
) -> list[SanskritTermRecord]:
    gloss_by_lemma: dict[str, str] = {}
    verses_by_lemma: dict[str, set[str]] = {}
    for vid, rows in per_verse.items():
        for row in rows:
            if is_sanskrit_stopword(row.surface):
                continue
            lemma = normalize_sanskrit_term(row.surface)
            if not lemma:
                continue
            gloss_by_lemma.setdefault(lemma, row.gloss)
            verses_by_lemma.setdefault(lemma, set()).add(vid)
    return [
        SanskritTermRecord(
            lemma,
            gloss_by_lemma[lemma],
            tuple(sorted(verses_by_lemma[lemma], key=_verse_id_sort_key)),
        )
        for lemma in sorted(verses_by_lemma)
    ]


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

# Epithets are modeled as Epithet nodes, so exclude them from SanskritTerm.
_EPITHET_STOPSET: frozenset[str] = frozenset(
    normalize_sanskrit_term(epithet)
    for epithets in EPITHETS.values()
    for epithet in epithets
)

CAST_EDGES: list[tuple[str, str, str]] = [
    ("Krishna", "CHARIOTEER_OF", "Arjuna"),
    ("Sanjaya", "NARRATES_TO", "Dhritarashtra"),
]

# Small curated gazetteer: lowercased gloss-name variant -> canonical character.
# Only the *names* are curated; which verse mentions whom is discovered from the
# Word Meanings glosses (see people_referenced_in_glosses).
PRINCIPALS: dict[str, str] = {
    "arjun": "Arjuna",
    "krishna": "Krishna",
    "sanjaya": "Sanjaya",
    "dhritarashtra": "Dhritarashtra",
    "bheem": "Bhima", "bhima": "Bhima",
    "bhishma": "Bhishma",
    "drona": "Drona",
    "duryodhan": "Duryodhana",
    "karna": "Karna",
    "yudhishthir": "Yudhishthira",
    "nakul": "Nakula",
    "sahadev": "Sahadeva",
    "drupad": "Drupada",
    "virat": "Virata",
    "satyaki": "Satyaki",
    "abhimanyu": "Abhimanyu",
    "kripa": "Kripa",
    "ashvatthama": "Ashvatthama", "ashwatthama": "Ashvatthama",
    "vikarna": "Vikarna",
}


def people_referenced_in_glosses(
    rows: Iterable[WordMeaning], principals: Mapping[str, str]
) -> set[str]:
    found: set[str] = set()
    for row in rows:
        gloss = row.gloss.lower()
        for needle, canonical in principals.items():
            if needle in gloss:
                found.add(canonical)
    return found


# 'X uvacha' speaker markers: substring of the normalized surface -> speaker.
# Surface is reliable; the gloss wording varies ("the Supreme Divine Personality").
_SPEAKER_MARKERS: dict[str, str] = {
    "bhagavan": "Krishna",
    "arjuna": "Arjuna",
    "sanjaya": "Sanjaya",
    "dhritarashtra": "Dhritarashtra",
}


def speaker_from_word_meanings(rows: Iterable[WordMeaning]) -> str | None:
    for row in rows:
        key = _clean_sanskrit_key(row.surface)
        if "uvacha" not in key:
            continue
        for needle, name in _SPEAKER_MARKERS.items():
            if needle in key:
                return name
    return None

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


def sanskrit_term_constraint_ops() -> list[Op]:
    return [(
        "CREATE CONSTRAINT sanskrit_term_lemma IF NOT EXISTS "
        "FOR (t:SanskritTerm) REQUIRE t.lemma IS UNIQUE",
        {},
    )]


def sanskrit_term_ops(records: Iterable[SanskritTermRecord]) -> list[Op]:
    ops: list[Op] = []
    for rec in records:
        ops.append((
            "MERGE (t:SanskritTerm {lemma: $lemma}) SET t.gloss = $gloss",
            {"lemma": rec.lemma, "gloss": rec.gloss},
        ))
        ops.append((
            "MATCH (t:SanskritTerm {lemma: $lemma}) "
            "UNWIND $verse_ids AS vid "
            "MATCH (v:Verse {id: vid}) "
            "MERGE (v)-[:CONTAINS_TERM]->(t)",
            {"lemma": rec.lemma, "verse_ids": list(rec.verse_ids)},
        ))
    return ops


def verse_text_ops(enrichment: Mapping[str, tuple[str, str]]) -> list[Op]:
    return [
        (
            "MATCH (v:Verse {id: $id}) "
            "SET v.sanskrit = $sanskrit, v.transliteration = $transliteration",
            {"id": vid, "sanskrit": sanskrit, "transliteration": translit},
        )
        for vid, (sanskrit, translit) in enrichment.items()
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


def theme_ops(themes: dict[str, dict] = THEMES) -> list[Op]:
    ops: list[Op] = []
    for name, spec in themes.items():
        ops.append(
            (
                "MERGE (th:Theme {name: $name}) "
                "SET th.label = $label, th.category = $category",
                {"name": name, "label": spec["label"], "category": spec["category"]},
            )
        )
        ops.append(
            (
                "MATCH (th:Theme {name: $name}) "
                "MATCH (t:Term) WHERE t.lemma IN $lemmas "
                "MERGE (th)-[:INCLUDES_TERM]->(t)",
                {"name": name, "lemmas": spec["lemmas"]},
            )
        )
        ops.append(
            (
                "MATCH (th:Theme {name: $name}) "
                "MATCH (v:Verse)-[m:MENTIONS_TERM]->(t:Term) "
                "WHERE t.lemma IN $lemmas "
                "WITH v, th, sum(m.count) AS w "
                "MERGE (v)-[r:MENTIONS_THEME]->(th) "
                "SET r.weight = w",
                {"name": name, "lemmas": spec["lemmas"]},
            )
        )
    return ops


# Curated concepts grounded in the Sanskrit term layer: each maps to the
# SanskritTerm lemmas that start with one of its prefixes (inflected variants).
CONCEPTS: dict[str, dict] = {
    # metaphysics
    "atman": {"label": "Ātman — the Self", "category": "metaphysics", "prefixes": ["atman", "atma"]},
    "brahman": {"label": "Brahman — the Absolute", "category": "metaphysics", "prefixes": ["brahma"]},
    "purusha": {"label": "Puruṣa — cosmic spirit", "category": "metaphysics", "prefixes": ["purush"]},
    "prakriti": {"label": "Prakṛti — material nature", "category": "metaphysics", "prefixes": ["prakrit"]},
    "moksha": {"label": "Mokṣa — liberation", "category": "metaphysics", "prefixes": ["moksha", "moksh", "mukti"]},
    # psychology
    "manas": {"label": "Manas — the mind", "category": "psychology", "prefixes": ["manas", "manah"]},
    "buddhi": {"label": "Buddhi — intellect", "category": "psychology", "prefixes": ["buddh"]},
    "indriya": {"label": "Indriya — the senses", "category": "psychology", "prefixes": ["indriy"]},
    "ahankara": {"label": "Ahaṅkāra — ego", "category": "psychology", "prefixes": ["ahankar"]},
    "deha": {"label": "Deha — the body", "category": "psychology", "prefixes": ["deha", "dehi", "dehe"]},
    "kama": {"label": "Kāma — desire", "category": "psychology", "prefixes": ["kama"]},
    "krodha": {"label": "Krodha — anger", "category": "psychology", "prefixes": ["krodh"]},
    # gunas
    "sattva": {"label": "Sattva — goodness", "category": "guna", "prefixes": ["sattv"]},
    "rajas": {"label": "Rajas — passion", "category": "guna", "prefixes": ["rajas", "rajo"]},
    "tamas": {"label": "Tamas — ignorance", "category": "guna", "prefixes": ["tamas", "tamo", "tamah", "tama"]},
    "guna": {"label": "Guṇa — qualities of nature", "category": "guna", "prefixes": ["guna"]},
    # paths / practice
    "karma": {"label": "Karma — action", "category": "path", "prefixes": ["karma"]},
    "jnana": {"label": "Jñāna — knowledge", "category": "path", "prefixes": ["jnan"]},
    "yoga": {"label": "Yoga — discipline", "category": "path", "prefixes": ["yoga", "yogi", "yogin"]},
    "dhyana": {"label": "Dhyāna — meditation", "category": "path", "prefixes": ["dhyan"]},
    "bhakti": {"label": "Bhakti — devotion", "category": "devotion", "prefixes": ["bhakt"]},
    "dharma": {"label": "Dharma — duty", "category": "ethics", "prefixes": ["dharma"]},
}


def concept_constraint_ops() -> list[Op]:
    return [(
        "CREATE CONSTRAINT concept_name IF NOT EXISTS "
        "FOR (c:Concept) REQUIRE c.name IS UNIQUE",
        {},
    )]


def concept_ops(concepts: dict[str, dict] = CONCEPTS) -> list[Op]:
    ops: list[Op] = []
    for name, spec in concepts.items():
        prefixes = spec["prefixes"]
        ops.append((
            "MERGE (c:Concept {name: $name}) "
            "SET c.label = $label, c.category = $category",
            {"name": name, "label": spec["label"], "category": spec["category"]},
        ))
        ops.append((
            "MATCH (c:Concept {name: $name}) "
            "MATCH (t:SanskritTerm) "
            "WHERE any(p IN $prefixes WHERE t.lemma STARTS WITH p) "
            "MERGE (t)-[:INSTANCE_OF]->(c)",
            {"name": name, "prefixes": prefixes},
        ))
        ops.append((
            "MATCH (c:Concept {name: $name}) "
            "MATCH (v:Verse)-[:CONTAINS_TERM]->(t:SanskritTerm) "
            "WHERE any(p IN $prefixes WHERE t.lemma STARTS WITH p) "
            "WITH v, c, count(DISTINCT t) AS w "
            "MERGE (v)-[r:EXPRESSES_CONCEPT]->(c) "
            "SET r.weight = w",
            {"name": name, "prefixes": prefixes},
        ))
    return ops


def concept_theme_alignment_ops(
    concepts: dict[str, dict] = CONCEPTS,
    themes: dict[str, dict] = THEMES,
) -> list[Op]:
    """Bridge the Sanskrit concept layer to the English theme index on shared names."""
    shared = sorted(set(concepts) & set(themes))
    return [
        (
            "MATCH (c:Concept {name: $name}), (t:Theme {name: $name}) "
            "MERGE (c)-[:ALIGNS_WITH]->(t)",
            {"name": name},
        )
        for name in shared
    ]


def character_constraint_ops() -> list[Op]:
    return [(
        "CREATE CONSTRAINT character_name IF NOT EXISTS "
        "FOR (c:Character) REQUIRE c.name IS UNIQUE",
        {},
    )]


def character_ops(
    mentions: Mapping[str, Iterable[str]],
    person_names: set[str] | None = None,
) -> list[Op]:
    principals = person_names if person_names is not None else {p["name"] for p in PERSONS}
    ops: list[Op] = []
    # every Person is also a Character; Person stays as the dialogue-role marker.
    for name in sorted(principals):
        ops.append(("MATCH (p:Person {name: $name}) SET p:Character", {"name": name}))
    seen: set[str] = set(principals)
    for chars in mentions.values():
        for name in chars:
            if name in seen:
                continue
            seen.add(name)
            ops.append(("MERGE (:Character {name: $name})", {"name": name}))
    for vid, chars in mentions.items():
        for name in chars:
            ops.append((
                "MATCH (v:Verse {id: $id}), (c:Character {name: $name}) "
                "MERGE (v)-[:MENTIONS_CHARACTER]->(c)",
                {"id": vid, "name": name},
            ))
    return ops


# --- Conches: the named war-conches of Chapter 1 (verses 15-16) ---

# gloss-name variant (lowercased) -> canonical conch name.
CONCH_ALIASES: dict[str, str] = {
    "panchajanya": "Panchajanya",
    "devadutta": "Devadatta", "devadatta": "Devadatta",
    "paundra": "Paundra",
    "anantavijay": "Anantavijaya", "anantavijaya": "Anantavijaya",
    "sughosh": "Sughosha", "sughosha": "Sughosha",
    "manipushpak": "Manipushpa", "manipushpaka": "Manipushpa", "manipushpa": "Manipushpa",
}

# conch -> the warrior who sounds it (attested in Ch.1 v15-16).
CONCH_OWNERS: dict[str, str] = {
    "Panchajanya": "Krishna",
    "Devadatta": "Arjuna",
    "Paundra": "Bhima",
    "Anantavijaya": "Yudhishthira",
    "Sughosha": "Nakula",
    "Manipushpa": "Sahadeva",
}

_CONCH_NAME_RE = re.compile(r"named\s+([A-Za-z]+)(?:\s+and\s+([A-Za-z]+))?")


def conch_names_in_gloss(gloss: str) -> list[str]:
    if "conch" not in gloss.lower():
        return []
    found: list[str] = []
    for match in _CONCH_NAME_RE.finditer(gloss):
        for raw in match.groups():
            if raw is None:
                continue
            canonical = CONCH_ALIASES.get(raw.lower())
            if canonical is not None and canonical not in found:
                found.append(canonical)
    return found


def conches_in_glosses(rows: Iterable[WordMeaning]) -> set[str]:
    found: set[str] = set()
    for row in rows:
        found.update(conch_names_in_gloss(row.gloss))
    return found


def conch_constraint_ops() -> list[Op]:
    return [(
        "CREATE CONSTRAINT conch_name IF NOT EXISTS "
        "FOR (c:Conch) REQUIRE c.name IS UNIQUE",
        {},
    )]


def conch_ops(
    mentions: Mapping[str, Iterable[str]],
    owners: Mapping[str, str] = CONCH_OWNERS,
) -> list[Op]:
    ops: list[Op] = []
    seen: set[str] = set()
    for conches in mentions.values():
        for name in conches:
            if name in seen:
                continue
            seen.add(name)
            ops.append((
                "MERGE (c:Conch {name: $name}) SET c.kind = 'conch'",
                {"name": name},
            ))
            owner = owners.get(name)
            if owner is not None:
                ops.append((
                    "MERGE (ch:Character {name: $owner}) "
                    "WITH ch MATCH (c:Conch {name: $name}) "
                    "MERGE (ch)-[:SOUNDS_CONCH]->(c)",
                    {"name": name, "owner": owner},
                ))
    for vid, conches in mentions.items():
        for name in conches:
            ops.append((
                "MATCH (v:Verse {id: $id}), (c:Conch {name: $name}) "
                "MERGE (v)-[:NAMES_CONCH]->(c)",
                {"id": vid, "name": name},
            ))
    return ops


# --- Vibhuti: Krishna's explicit "I am ..." glories of Chapter 10 ---

def is_vibhuti_declaration(chapter: int, rows: Iterable[WordMeaning]) -> bool:
    """True for a Ch.10 verse where Krishna explicitly declares 'I am' (asmi)."""
    if chapter != 10:
        return False
    return any(_clean_sanskrit_key(row.surface) == "asmi" for row in rows)


def vibhuti_constraint_ops() -> list[Op]:
    return [(
        "CREATE CONSTRAINT vibhuti_name IF NOT EXISTS "
        "FOR (vb:Vibhuti) REQUIRE vb.name IS UNIQUE",
        {},
    )]


def vibhuti_ops(verse_ids: Iterable[str]) -> list[Op]:
    ops: list[Op] = [
        (
            "MERGE (vb:Vibhuti {name: 'divine-glories'}) "
            "SET vb.label = 'Divine Glories (Vibhūti)', vb.chapter = 10",
            {},
        ),
        (
            "MERGE (k:Character {name: 'Krishna'}) "
            "WITH k MATCH (vb:Vibhuti {name: 'divine-glories'}) "
            "MERGE (k)-[:MANIFESTS_AS]->(vb)",
            {},
        ),
    ]
    for vid in verse_ids:
        ops.append((
            "MATCH (v:Verse {id: $id}), (vb:Vibhuti {name: 'divine-glories'}) "
            "MERGE (v)-[:DECLARES_VIBHUTI]->(vb)",
            {"id": vid},
        ))
    return ops


@dataclass(frozen=True)
class EmbeddingConfig:
    model_id: str = "sentence-transformers/all-mpnet-base-v2"
    revision: str = "e8c3b32edf5434bc2275fc9bab85f82640a19130"
    dimensions: int = 768
    top_k: int = 5
    threshold: float = 0.50


@dataclass(frozen=True)
class SimilarityPair:
    a_id: str
    b_id: str
    score: float
    rank_a: int | None
    rank_b: int | None
    mutual: bool


def verse_order_key(verse_id: str) -> tuple[int, int]:
    chapter, verse = verse_id.split(".", maxsplit=1)
    return int(chapter), int(verse)


def canonical_pair(a_id: str, b_id: str) -> tuple[str, str]:
    return tuple(sorted((a_id, b_id), key=verse_order_key))


def build_similarity_pairs(
    ids: list[str], similarity_matrix: np.ndarray, top_k: int, threshold: float
) -> list[SimilarityPair]:
    matrix = np.asarray(similarity_matrix)
    if matrix.shape != (len(ids), len(ids)):
        raise ValueError("similarity matrix shape must match verse ids")
    if not np.allclose(matrix, matrix.T, atol=1e-8):
        raise ValueError("similarity matrix must be symmetric")

    directed: dict[tuple[str, str], tuple[float, int]] = {}
    for source_idx, source_id in enumerate(ids):
        candidates = [idx for idx in np.argsort(-matrix[source_idx], kind="stable") if idx != source_idx]
        for rank, target_idx in enumerate(candidates[:top_k], start=1):
            score = float(matrix[source_idx, target_idx])
            if score >= threshold:
                directed[(source_id, ids[target_idx])] = (score, rank)

    pair_data: dict[tuple[str, str], dict] = {}
    for (source_id, target_id), (score, rank) in directed.items():
        a_id, b_id = canonical_pair(source_id, target_id)
        data = pair_data.setdefault(
            (a_id, b_id), {"score": score, "rank_a": None, "rank_b": None}
        )
        data["score"] = max(data["score"], score)
        if source_id == a_id:
            data["rank_a"] = rank
        else:
            data["rank_b"] = rank

    return [
        SimilarityPair(
            a_id=a_id,
            b_id=b_id,
            score=data["score"],
            rank_a=data["rank_a"],
            rank_b=data["rank_b"],
            mutual=data["rank_a"] is not None and data["rank_b"] is not None,
        )
        for (a_id, b_id), data in sorted(
            pair_data.items(), key=lambda item: (verse_order_key(item[0][0]), verse_order_key(item[0][1]))
        )
    ]


VECTOR_INDEX_NAME = "verse_translation_embeddings"


def embedding_ops(rows: list[dict], config: EmbeddingConfig) -> list[Op]:
    return [
        (
            "MATCH (v:Verse {id: $id}) "
            "CALL db.create.setNodeVectorProperty(v, 'embedding', $embedding) "
            "SET v.embedding_model = $model, "
            "v.embedding_revision = $revision, "
            "v.embedding_dimension = $dimension, "
            "v.embedding_input_sha256 = $input_sha256",
            {
                "id": row["id"],
                "embedding": row["embedding"],
                "model": config.model_id,
                "revision": config.revision,
                "dimension": config.dimensions,
                "input_sha256": row["input_sha256"],
            },
        )
        for row in rows
    ]


def vector_index_ops(config: EmbeddingConfig) -> list[Op]:
    return [
        (
            "CREATE VECTOR INDEX verse_translation_embeddings IF NOT EXISTS "
            "FOR (v:Verse) ON (v.embedding) "
            f"OPTIONS {{indexConfig: {{`vector.dimensions`: {config.dimensions}, "
            "`vector.similarity_function`: 'cosine'}}",
            {},
        )
    ]


def clear_similarity_ops() -> list[Op]:
    return [("MATCH ()-[r:SIMILAR_TO]->() DELETE r", {})]


def similarity_ops(pairs: list[SimilarityPair], config: EmbeddingConfig) -> list[Op]:
    return [
        (
            "MATCH (a:Verse {id: $a_id}), (b:Verse {id: $b_id}) "
            "MERGE (a)-[r:SIMILAR_TO]->(b) "
            "SET r.score = $score, r.mutual = $mutual, "
            "r.rank_a = $rank_a, r.rank_b = $rank_b, "
            "r.model = $model, r.revision = $revision, "
            "r.top_k = $top_k, r.threshold = $threshold",
            {
                "a_id": pair.a_id,
                "b_id": pair.b_id,
                "score": pair.score,
                "mutual": pair.mutual,
                "rank_a": pair.rank_a,
                "rank_b": pair.rank_b,
                "model": config.model_id,
                "revision": config.revision,
                "top_k": config.top_k,
                "threshold": config.threshold,
            },
        )
        for pair in pairs
    ]


CANDIDATE_THRESHOLDS = (0.50, 0.55, 0.60, 0.65, 0.70, 0.75)


@dataclass(frozen=True)
class ThresholdStats:
    threshold: float
    covered_fraction: float
    cross_chapter_themes: frozenset[str]
    pair_count: int
    mutual_count: int


def similarity_score_quantiles(scores: list[float]) -> dict[str, float]:
    """Compute distribution quantiles for similarity scores.

    Returns dict with keys: min, p05, p10, p25, p50, p75, p90, p95, max.
    """
    if not scores:
        raise ValueError("scores must not be empty")
    values = np.asarray(scores, dtype=float)
    percentiles = np.percentile(values, [0, 5, 10, 25, 50, 75, 90, 95, 100])
    return dict(zip(("min", "p05", "p10", "p25", "p50", "p75", "p90", "p95", "max"), percentiles.tolist()))


def evaluate_thresholds(
    ids: list[str],
    similarity_matrix: np.ndarray,
    top_k: int,
    thresholds: tuple[float, ...],
    chapters: dict[str, int],
    themes_by_id: dict[str, set[str]],
) -> list[ThresholdStats]:
    """Evaluate coverage and cross-chapter themes for each threshold.

    Returns ThresholdStats per threshold with coverage fraction, pair counts,
    and cross-chapter theme intersection.
    """
    if not ids:
        raise ValueError("ids must not be empty")
    missing = sorted(set(ids) - chapters.keys(), key=verse_order_key)
    if missing:
        raise ValueError(f"chapters missing verse ids: {missing}")
    results: list[ThresholdStats] = []
    for threshold in thresholds:
        pairs = build_similarity_pairs(ids, similarity_matrix, top_k, threshold)
        covered = {verse_id for pair in pairs for verse_id in (pair.a_id, pair.b_id)}
        cross_themes: set[str] = set()
        for pair in pairs:
            if chapters[pair.a_id] != chapters[pair.b_id]:
                cross_themes.update(themes_by_id.get(pair.a_id, set()) & themes_by_id.get(pair.b_id, set()))
        results.append(
            ThresholdStats(
                threshold=threshold,
                covered_fraction=len(covered) / len(ids),
                cross_chapter_themes=frozenset(cross_themes),
                pair_count=len(pairs),
                mutual_count=sum(pair.mutual for pair in pairs),
            )
        )
    return results


def select_similarity_threshold(stats: list[ThresholdStats], all_themes: set[str]) -> float:
    """Select highest threshold meeting coverage and theme completeness.

    Primary: highest threshold with >=90% coverage and all cross-chapter themes.
    Fallback: highest threshold with >=90% coverage if no complete candidate.
    """
    coverage_ok = [item for item in stats if item.covered_fraction >= 0.90]
    if not coverage_ok:
        raise ValueError("no candidate threshold retains 90% verse coverage")
    complete = [item for item in coverage_ok if all_themes <= item.cross_chapter_themes]
    candidates = complete or coverage_ok
    return max(item.threshold for item in candidates)

