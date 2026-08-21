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

### Theme layer (C1)

An optional curated layer over the core graph:

- **Node** `Theme` (`name`, `label`, `category`) — 13 Gita themes (karma,
  dharma, bhakti, jñāna, yoga, moksha, ātman, brahman, guṇa, saṃsāra,
  detachment, senses-mind, sacrifice-austerity).
- **Relationships** `(Verse)-[:MENTIONS_THEME {weight}]->(Theme)` and
  `(Theme)-[:INCLUDES_TERM]->(Term)`.

Themes are derived **deterministically** from the `Term` layer: each theme is
defined by a set of lemmas, and a verse links to a theme when it mentions those
terms. `weight` is the sum of the matched terms' per-verse counts.

Run **after** `gita_kg.ipynb`:

```bash
uv run jupyter nbconvert --to notebook --execute --inplace gita-knowledge-graph/themes_kg.ipynb
```

Sample query — the verses most about a theme:

```cypher
MATCH (v:Verse)-[r:MENTIONS_THEME]->(:Theme {name: 'karma'})
RETURN v.id, r.weight ORDER BY r.weight DESC LIMIT 10
```

- **Spec:** `docs/superpowers/specs/2026-08-21-gita-kg-c1-themes-design.md`

### Semantic similarity (C2)

An optional semantic layer that adds reproducible verse-to-verse similarity discovery and vector search:

- **Model:** `sentence-transformers/all-mpnet-base-v2` at revision `e8c3b32edf5434bc2275fc9bab85f82640a19130` (pinned for reproducibility).
- **Input:** `Verse.translation` text only. No Sanskrit, transliteration, chapter titles, or C1 theme labels are included in embeddings.
- **Embeddings:** Normalized 768-dimensional vectors stored on each `Verse` node with metadata (`embedding_model`, `embedding_revision`, `embedding_dimension`, `embedding_input_sha256`).
- **Vector index:** Native Neo4j cosine vector index named `verse_translation_embeddings` on `Verse.embedding` for dynamic nearest-neighbour search.
- **Relationship:** `(Verse)-[:SIMILAR_TO {score, mutual, rank_a, rank_b, model, revision, top_k, threshold}]->(Verse)` — canonical unordered pairs selected via calibrated union top-5.
  - `score`: cosine similarity (symmetric).
  - `mutual`: true when both verses select each other in their top-5.
  - `rank_a`, `rank_b`: endpoint ranks in each other's top-5 lists (1-based; one may be null for one-sided selections).
  - Canonical direction is ascending numeric `(chapter, verse)` order (`2.1` precedes `10.1`).
  - **Always query undirected:** `MATCH (a:Verse)-[r:SIMILAR_TO]-(b:Verse)`

**Calibration:** The notebook computes similarity at candidate thresholds (0.50–0.75), evaluates verse coverage and cross-chapter theme edges, and selects the highest threshold that retains ≥90% of verses. A manual quality gate requires sample inspection before edges are loaded.

**Run order** (after v1 base graph):

```bash
uv run jupyter nbconvert --to notebook --execute --inplace gita-knowledge-graph/gita_kg.ipynb
uv run jupyter nbconvert --to notebook --execute --inplace gita-knowledge-graph/themes_kg.ipynb
uv run jupyter nbconvert --to notebook --execute --inplace gita-knowledge-graph/similarity_kg.ipynb
```

**Prerequisites:** The exact pinned model `all-mpnet-base-v2` revision `e8c3b32...` must be accessible in the Hugging Face cache or downloadable. On networks where Hugging Face downloads are blocked, ensure the model is pre-cached. The notebook will fail loudly if the model cannot be loaded.

**Vector search query** — find semantically similar verses at runtime:

```cypher
MATCH (source:Verse {id: $verse_id})
CALL db.index.vector.queryNodes(
  'verse_translation_embeddings',
  $limit,
  source.embedding
) YIELD node, score
WHERE node <> source
RETURN node.id AS verse, node.translation AS translation, score
ORDER BY score DESC
```

**Bloom queries:**

High-confidence similarity neighbourhood (mutual edges only, 1–2 hops):

```cypher
MATCH p=(a:Verse {id: $verse_id})-[r:SIMILAR_TO*1..2]-(b:Verse)
WHERE all(rel IN relationships(p) WHERE rel.mutual = true)
RETURN p
```

Cross-chapter related verses sharing a C1 theme:

```cypher
MATCH (a:Verse {id: $verse_id})-[r:SIMILAR_TO]-(b:Verse)
MATCH (a)-[:MENTIONS_THEME]->(th:Theme)<-[:MENTIONS_THEME]-(b)
WHERE a.chapter <> b.chapter
RETURN a, r, b, th
ORDER BY r.score DESC
```

- **Spec:** `docs/superpowers/specs/2026-08-21-gita-kg-c2-semantic-similarity-design.md`

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

### Standalone HTML visualization

No Neo4j UI needed — export an interactive Plotly graph to `exports/`:

```bash
uv run python gita-knowledge-graph/export_graph.py                 # backbone (no Term layer)
uv run python gita-knowledge-graph/export_graph.py --include-terms # full graph
```

Then open `exports/gita_graph_backbone.html` (or `_full.html`) in a browser.
`exports/` is gitignored.

