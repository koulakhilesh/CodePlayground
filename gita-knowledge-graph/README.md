# Bhagavad Gita Knowledge Graph

Loads the Bhagavad Gita (chapters, verses, speakers, addressees, epithets,
setting, lemmatized terms, and the Sanskrit Word Meanings) into a local Neo4j
database, then layers themes, Sanskrit-grounded concepts, the character cast,
the named war-conches, Krishna's Chapter 10 glories, and semantic similarity on
top. Everything is built by a single notebook, `gita_kg.ipynb`. A second
notebook, `gita_analysis.ipynb`, reads the finished graph and runs graph data
science over it (see [Analysis](#analysis-graph-data-science)).

## Ontology

See [ONTOLOGY.md](ONTOLOGY.md) for the full domain model: operating principles,
per-node/edge semantics, provenance, and known ontological tensions.

**Nodes:** `Text`, `Chapter` (`number`, `name`), `Verse`
(`id`, `chapter`, `verse`, `translation`, `sanskrit`, `transliteration`),
`Person` (`name`, `role`, `aliases`), `Epithet` (`name`), `Place` (`name`),
`Term` (`lemma`).

**Relationships:** `HAS_CHAPTER`, `HAS_VERSE`, `NEXT`, `SPOKEN_BY`,
`ADDRESSED_TO`, `USES_EPITHET`, `EPITHET_OF`, `SET_IN`, `CHARIOTEER_OF`,
`NARRATES_TO`, `MENTIONS_TERM` (with `count`).

### Sanskrit, concept, character & entity layers (v2)

Grounded directly in the Sanskrit Word Meanings of each verse:

- **`SanskritTerm`** (`lemma`) is the normalized Sanskrit vocabulary, linked
  `(Verse)-[:CONTAINS_TERM]->(SanskritTerm)`.
- **`Concept`** (`name`, `label`, `category`) covers 22 curated concepts grounded in
  the Sanskrit terms via `(SanskritTerm)-[:INSTANCE_OF]->(Concept)` and
  `(Verse)-[:EXPRESSES_CONCEPT {weight}]->(Concept)`. Concepts bridge to the
  English theme index on shared names via `(Concept)-[:ALIGNS_WITH]->(Theme)`.
- **`Character`** (`name`) is the cast discovered from the glosses, linked
  `(Verse)-[:MENTIONS_CHARACTER]->(Character)`. Every `Person` is also a
  `Character` (`Person` is the dialogue-role marker).
- **`Conch`** (`name`, `kind`) covers the six named war-conches of Chapter 1,
  `(Verse)-[:NAMES_CONCH]->(Conch)` and `(Character)-[:SOUNDS_CONCH]->(Conch)`.
- **`Vibhuti`** (`name`, `label`, `chapter`) holds Krishna's Chapter 10 glories: the
  verses that explicitly declare "I am …" (`asmi`), grouped via
  `(Verse)-[:DECLARES_VIBHUTI]->(Vibhuti)` and `(Character)-[:MANIFESTS_AS]->(Vibhuti)`.

### Theme layer (C1)

An optional curated layer over the core graph:

- **Node** `Theme` (`name`, `label`, `category`) covers 13 Gita themes (karma,
  dharma, bhakti, jñāna, yoga, moksha, ātman, brahman, guṇa, saṃsāra,
  detachment, senses-mind, sacrifice-austerity).
- **Relationships** `(Verse)-[:MENTIONS_THEME {weight}]->(Theme)` and
  `(Theme)-[:INCLUDES_TERM]->(Term)`.

Themes are derived **deterministically** from the `Term` layer: each theme is
defined by a set of lemmas, and a verse links to a theme when it mentions those
terms. `weight` is the sum of the matched terms' per-verse counts.

The theme layer is built as a section of `gita_kg.ipynb`, with no separate notebook.

Sample query, the verses most about a theme:

```cypher
MATCH (v:Verse)-[r:MENTIONS_THEME]->(:Theme {name: 'karma'})
RETURN v.id, r.weight ORDER BY r.weight DESC LIMIT 10
```

### Semantic similarity (C2)

An optional semantic layer that adds reproducible verse-to-verse similarity discovery and vector search:

- **Model:** `sentence-transformers/all-mpnet-base-v2` at revision `e8c3b32edf5434bc2275fc9bab85f82640a19130` (pinned for reproducibility).
- **Input:** `Verse.translation` text only. No Sanskrit, transliteration, chapter titles, or C1 theme labels are included in embeddings.
- **Embeddings:** Normalized 768-dimensional vectors stored on each `Verse` node with metadata (`embedding_model`, `embedding_revision`, `embedding_dimension`, `embedding_input_sha256`).
- **Vector index:** Native Neo4j cosine vector index named `verse_translation_embeddings` on `Verse.embedding` for dynamic nearest-neighbour search.
  - **Relationship:** `(Verse)-[:SIMILAR_TO {score, mutual, rank_a, rank_b, model, revision, top_k, threshold}]->(Verse)`, canonical unordered pairs selected via calibrated union top-5.
  - `score`: cosine similarity (symmetric).
  - `mutual`: true when both verses select each other in their top-5.
  - `rank_a`, `rank_b`: endpoint ranks in each other's top-5 lists (1-based; one may be null for one-sided selections).
  - Canonical direction is ascending numeric `(chapter, verse)` order (`2.1` precedes `10.1`).
  - **Always query undirected:** `MATCH (a:Verse)-[r:SIMILAR_TO]-(b:Verse)`

**Calibration:** The notebook computes similarity at candidate thresholds (0.50 to 0.75), evaluates verse coverage and cross-chapter theme edges, and selects the highest threshold that retains ≥90% of verses. A manual quality gate requires sample inspection before edges are loaded.

**Run order:** the similarity layer is the final section of `gita_kg.ipynb`, so
the whole graph (structure → Sanskrit → themes → concepts → characters →
weapons/vibhuti → similarity) builds in one pass:

```bash
uv run jupyter nbconvert --to notebook --execute --inplace gita-knowledge-graph/gita_kg.ipynb
```

**Prerequisites:** The exact pinned model `all-mpnet-base-v2` revision `e8c3b32...` must be accessible in the Hugging Face cache or from a local model directory. For offline loading, set this in the gitignored `.env`:

```dotenv
GITA_EMBEDDING_MODEL_PATH=~/Documents/embedding/all-mpnet-base-v2
```

The loader uses that directory with network access disabled for model resolution. Neo4j provenance still records the official model ID and pinned revision. The notebook fails immediately if the configured directory does not exist.

**Vector search query**, find semantically similar verses at runtime:

```cypher
MATCH (source:Verse {id: $verse_id})
MATCH (node:Verse)
SEARCH node IN (
  VECTOR INDEX verse_translation_embeddings
  FOR source.embedding
  LIMIT $limit
) SCORE AS score
WHERE node <> source
RETURN node.id AS verse, node.translation AS translation, score
ORDER BY score DESC
```

## How it works

- **Deterministic, two-tier parsing.** Structure (chapter/verse numbers, the
  `## Translation` body, the `"X said,"` speaker prefix) is exact string/regex
  work. The linguistic layer uses spaCy: a rule-based `EntityRuler` seeded with a
  controlled vocabulary tags epithets (not statistical NER), and lemmatization +
  POS tagging drive the `Term` layer.
- **Idempotent.** All writes are `MERGE` keyed on natural IDs, so re-running
  rebuilds the graph with no duplicates.
- **Sanskrit-grounded.** Beyond the English translation, the Sanskrit Word
  Meanings drive the `SanskritTerm`, `Concept`, `Character`, `Conch`, and
  `Vibhuti` layers; each verse also stores its `sanskrit` and `transliteration`.
  Embeddings (C2) still use the English `translation` only, by design.

## Prerequisites

- A local Neo4j instance. Set `NEO4J_DATABASE` to a database that exists on it.
  On Community/Desktop that is the default `neo4j`; a named `TheGitaProject`
  database requires Neo4j Enterprise.
- Verse source data at `data/TheGitaProject/Verses/ChapterNN/ChapterNNVerseNN.md`.
- Python deps installed (the pinned `en_core_web_sm` model is a declared
  dependency, so `uv sync` installs it, with no separate download step):

  ```bash
  uv sync
  ```

- A `.env` in this folder (copy `.env.example`) with your Neo4j credentials:

  ```bash
  cp gita-knowledge-graph/.env.example gita-knowledge-graph/.env
  # then edit .env and set NEO4J_PASSWORD (and URI/USER if not the defaults)
  ```

  `.env` is gitignored, so credentials never enter version control.

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

Unit tests run against committed fixtures with no Neo4j and no network.
`@pytest.mark.integration` tests load installed model artifacts, including
`en_core_web_sm` and the pinned sentence-transformer. Set
`GITA_EMBEDDING_MODEL_PATH` when the latter is stored outside the Hugging Face
cache.

## Analysis: Graph Data Science

Once the graph is built, `gita_analysis.ipynb` reads it (never writes to it) and
runs six analyses through the **Neo4j Graph Data Science (GDS)** library,
exporting an interactive Plotly HTML per analysis to `exports/` (gitignored):

1. **Verse communities:** Louvain (plus a Leiden cross-check) on the `SIMILAR_TO`
   network; shows that the semantic communities cut across chapter boundaries.
2. **Verse centrality:** PageRank (the semantic centre of gravity) and
   Betweenness (the bridge verses between clusters).
3. **Theme & concept correlation:** GDS Node Similarity (Jaccard over shared
   verses) on the reverse-projected `MENTIONS_THEME` / `EXPRESSES_CONCEPT`
   graphs; which ideas travel together.
4. **Character co-occurrence:** the social network of the cast named in the
   verses, sized by PageRank centrality.
5. **Narrative arc:** theme share traced along the 700-verse reading order
   (a descriptive sequence analysis, not a graph algorithm).
6. **Dialogue dynamics:** who speaks, to whom, chapter by chapter
   (also descriptive).

The split is deliberate: `gita_kg.ipynb` **writes** the graph (all `MERGE`,
idempotent), while `gita_analysis.ipynb` only **reads** it. It builds in-memory
GDS projections, streams the results, and drops them at the end, so analysis can
never mutate the graph.

**Correctness.** There is no separate test suite for the analysis; instead every
section ends with inline `assert`s that halt on mismatch: projection counts
equal the stored graph, similarity graphs are symmetric, community coverage is
total, the GDS Jaccard is re-derived from a plain Cypher count, and every
plotted number comes from the same dataframe (never hand-typed).

**Prerequisites:** a graph already built by `gita_kg.ipynb`, plus the **GDS
plugin** installed in Neo4j (Neo4j Desktop, then your DBMS, then Plugins, then
Graph Data Science; the open-source Community tier suffices). The
`graphdatascience` Python client is a declared dependency (`uv sync`).

**Run** (headless, from the repo root, after the graph is built):

```bash
uv run jupyter nbconvert --to notebook --execute --inplace gita-knowledge-graph/gita_analysis.ipynb
```

### Deep dives

Focused, post-oriented notebooks that build on the survey above:

- **`gita_verse_map.ipynb`**: the "shape of the Gita". Projects the 701 pinned
  verse embeddings into 2D with scikit-learn **t-SNE**, colours the map by GDS
  Louvain community and by chapter, then characterises each community by its
  most *distinctive* themes (lift over the global share), its top concept, and
  an exemplar verse nearest the community centroid. No extra dependency (t-SNE
  ships with scikit-learn; UMAP is avoided because `numba` lacks wheels on this
  project's Python). Exports `map_*.html` to `exports/`.

  ```bash
  uv run jupyter nbconvert --to notebook --execute --inplace gita-knowledge-graph/gita_verse_map.ipynb
  ```

- **`gita_speaker_signatures.ipynb`**: how the four voices (Krishna, Arjuna,
  Sanjaya, Dhritarashtra) differ. Speaking share, theme/concept *fingerprints*
  (lift over the whole text), and a **Dunning log-likelihood (G²) keyness**
  analysis, the standard corpus-linguistics test for the content words most
  over-represented in each voice. Read-only, no schema change; keyness is limited
  to the content-lemma `Term` layer. Exports `speaker_*.html` to `exports/`.

  ```bash
  uv run jupyter nbconvert --to notebook --execute --inplace gita-knowledge-graph/gita_speaker_signatures.ipynb
  ```

## Exploring in Neo4j Bloom

Open **Neo4j Desktop → your DBMS → Neo4j Bloom** (or the **Explore** tab in
Neo4j Workspace), connect to the `neo4j` database, and generate a perspective.
Keep the generated perspective as an admin view, then duplicate it into three
focused perspectives:

1. **Reading Structure:** include `Text`, `Chapter`, `Verse`, `Person`,
  `Epithet`, and `Place`. Keep structural relationships such as `HAS_CHAPTER`,
  `HAS_VERSE`, `NEXT`, `SPOKEN_BY`, `ADDRESSED_TO`, `USES_EPITHET`, and
  `SET_IN`. Exclude `Term`, `Theme`, and `SIMILAR_TO`.
2. **Theme Map:** include `Chapter`, `Verse`, and `Theme`, with `HAS_VERSE`
  and `MENTIONS_THEME`. This makes cross-chapter thematic clusters visible
  without semantic edges overwhelming the scene.
3. **Semantic Neighbourhood:** include `Verse`, `Theme`, and `Chapter`, with
  `SIMILAR_TO`, `MENTIONS_THEME`, and `HAS_VERSE`. Start from one verse and
  expand one or two hops instead of loading every similarity edge.

Use `id` as the `Verse` caption, `number` for `Chapter`, `name` for `Theme`,
`Person`, `Epithet`, and `Place`, and `lemma` for `Term`. In the semantic
perspective, caption `SIMILAR_TO` by `score`; style `mutual = true` edges with a
strong color and non-mutual edges in light gray. Keep verse nodes compact,
theme nodes larger, and chapter nodes visually distinct. Avoid using the
768-value `embedding` property in captions or styling.

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

**Mutual semantic neighbourhood of verse $verse_id**
```cypher
MATCH p=(a:Verse {id: $verse_id})-[r:SIMILAR_TO*1..2]-(b:Verse)
WHERE all(rel IN relationships(p) WHERE rel.mutual = true)
RETURN p
```

**Cross-chapter theme bridges for verse $verse_id**
```cypher
MATCH (a:Verse {id: $verse_id})-[r:SIMILAR_TO]-(b:Verse)
MATCH (a)-[:MENTIONS_THEME]->(th:Theme)<-[:MENTIONS_THEME]-(b)
WHERE a.chapter <> b.chapter
RETURN a, r, b, th
ORDER BY r.score DESC
```

### Viewing the whole graph

The full graph (several thousand nodes once the `Term` and `SanskritTerm` layers
are included) is a hairball. Prefer the **structural backbone**, everything
except the term layers, which is legible:

```cypher
// Backbone: Text, Chapters, Verses, Persons, Epithets, Place, Characters, Conches
MATCH (n)-[r]->(m)
WHERE NOT n:Term AND NOT m:Term AND NOT n:SanskritTerm AND NOT m:SanskritTerm
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

No Neo4j UI needed. Export an interactive Plotly graph to `exports/`:

```bash
uv run python gita-knowledge-graph/export_graph.py                 # backbone (no Term/SanskritTerm layers)
uv run python gita-knowledge-graph/export_graph.py --include-terms # full graph
```

Then open `exports/gita_graph_backbone.html` (or `_full.html`) in a browser.
`exports/` is gitignored.

