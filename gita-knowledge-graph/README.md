# Bhagavad Gita Knowledge Graph

Loads the Bhagavad Gita's structure — chapters, verses, speakers, addressees,
epithets, setting, and lemmatized terms — from the English translations into a
local Neo4j `TheGitaProject` database. Structural core (v1), built so a thematic
layer (themes / concepts / similarity) can be added later without rework.

- **Design spec:** `docs/superpowers/specs/2026-08-20-gita-knowledge-graph-design.md`

## Ontology

**Nodes:** `Text`, `Chapter` (`number`, `name`), `Verse`
(`id`, `chapter`, `verse`, `translation`), `Person` (`name`, `role`, `aliases`),
`Epithet` (`name`), `Place` (`name`), `Term` (`lemma`).

**Relationships:** `HAS_CHAPTER`, `HAS_VERSE`, `NEXT`, `SPOKEN_BY`,
`ADDRESSED_TO`, `USES_EPITHET`, `EPITHET_OF`, `SET_IN`, `CHARIOTEER_OF`,
`NARRATES_TO`, `MENTIONS_TERM` (with `count`).

## How it works

- **Deterministic, two-tier parsing.** Structure (chapter/verse numbers, the
  `## Translation` body, the `"X said,"` speaker prefix) is exact string/regex
  work. The linguistic layer uses spaCy: a rule-based `EntityRuler` seeded with a
  controlled vocabulary tags epithets (not statistical NER), and lemmatization +
  POS tagging drive the `Term` layer.
- **Idempotent.** All writes are `MERGE` keyed on natural IDs, so re-running
  rebuilds the graph with no duplicates.
- **English only.** Sanskrit, transliteration, and word-meaning sections are
  ignored.

## Prerequisites

- A local Neo4j instance. Set `NEO4J_DATABASE` to a database that exists on it —
  on Community/Desktop that is the default `neo4j`; a named `TheGitaProject`
  database requires Neo4j Enterprise.
- Verse source data at `data/TheGitaProject/Verses/ChapterNN/ChapterNNVerseNN.md`.
- Python deps installed (the pinned `en_core_web_sm` model is a declared
  dependency, so `uv sync` installs it \u2014 no separate download step):

  ```bash
  uv sync
  ```

- A `.env` in this folder (copy `.env.example`) with your Neo4j credentials:

  ```bash
  cp gita-knowledge-graph/.env.example gita-knowledge-graph/.env
  # then edit .env and set NEO4J_PASSWORD (and URI/USER if not the defaults)
  ```

  `.env` is gitignored — credentials never enter version control.

## Run

Execute the notebook (headless, from the repo root):

```bash
uv run jupyter nbconvert --to notebook --execute --inplace gita-knowledge-graph/gita_kg.ipynb
```

Expected: ~700 `Verse` nodes, zero verses missing `SPOKEN_BY` / `ADDRESSED_TO`,
and non-empty `Term` / epithet counts. Re-running yields the same counts
(idempotent).

## Test

```bash
uv run pytest gita-knowledge-graph -v
```

Unit tests run against committed fixtures with no Neo4j and no network; the one
`@pytest.mark.integration` test loads `en_core_web_sm`.

## Exploring in Neo4j Bloom

Open **Neo4j Desktop → your DBMS → Neo4j Bloom** (or the **Explore** tab in
Neo4j Workspace), connect to the `neo4j` database, and **Generate** a
perspective. Set captions: `Verse`→`id`, `Person`/`Chapter`/`Epithet`/`Place`→
`name`, `Term`→`lemma`.

### Saved search phrases (Perspective → Search phrases → Create)

**Verses spoken by $speaker**
```cypher
MATCH (v:Verse)-[:SPOKEN_BY]->(p:Person {name: $speaker})
RETURN v, p
```

**Epithets used for $person**
```cypher
MATCH (v:Verse)-[:USES_EPITHET]->(e:Epithet)-[:EPITHET_OF]->(p:Person {name: $person})
RETURN v, e, p
```

**Reading path through chapter $num**
```cypher
MATCH path = (:Chapter {number: $num})-[:HAS_VERSE]->(v)-[:NEXT*0..]->()
RETURN path
```

### Viewing the whole graph

The full graph (~1900 nodes incl. the `Term` layer) is a hairball. Prefer the
**structural backbone** — everything except terms — which is legible:

```cypher
// Backbone: Text, Chapters, Verses, Persons, Epithets, Place
MATCH (n)-[r]->(m)
WHERE NOT n:Term AND NOT m:Term
RETURN n, r, m
```

To see truly everything (raise Browser's node limit first, Settings → "Max
nodes to display"):

```cypher
MATCH (n)-[r]->(m) RETURN n, r, m
```

Tip: in Bloom, search `Text`, then right-click → **Expand** by specific
relationship types (`HAS_CHAPTER`, `HAS_VERSE`, `SPOKEN_BY`) to grow the view
deliberately instead of loading the term hairball at once.

