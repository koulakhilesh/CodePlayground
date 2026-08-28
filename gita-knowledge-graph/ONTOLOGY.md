# Bhagavad Gita Knowledge Graph: Ontology

This document defines the domain model behind the graph: what each node and
relationship *means*, where it comes from, and the rules the graph obeys. It is
the reference for anyone reading, querying, or extending the graph.

Counts below reflect the current build (701 verses, 18 chapters).

---

## Operating principles

These are the invariants the whole graph is built on. If a change breaks one of
them, it is a bug.

1. **The verse text is the ground truth.** Every derived fact traces back to a
   verse file under `data/TheGitaProject/Verses/`. Two sources are used:
   the English **Translation** and the Sanskrit **Word Meanings** table.
2. **Provenance is explicit.** Every node/edge is one of four kinds:
   - **Seed:** hand-curated constants (the 4 framing persons, chapter names,
     theme/concept taxonomies). These encode editorial knowledge not literally
     parseable from a single verse.
   - **Extracted:** read directly from a verse (speaker prefix, epithets,
     Sanskrit terms, named conches, character glosses).
   - **Derived:** a deterministic function of extracted data (themes and
     concepts mapped from the term layers).
   - **Computed:** produced by the pinned embedding model (vectors, similarity).
3. **Idempotent.** All writes are `MERGE` keyed on a natural identity. Re-running
   the notebook reproduces the same graph with no duplicates.
4. **English drives embeddings; Sanskrit drives meaning.** Similarity vectors are
   computed from the English translation only (reproducibility). Concepts and
   characters are grounded in the Sanskrit Word Meanings.
5. **Manual quality gate for similarity.** `SIMILAR_TO` edges are only written
   after a human approves the calibrated threshold (`QUALITY_APPROVED`).

---

## Node catalog

Identity = the property that uniquely keys the node (the `MERGE` key).

| Label | Identity | Properties | Provenance | Count | Meaning |
|-------|----------|-----------|------------|------:|---------|
| `Text` | `name` | `name` | Seed | 1 | The scripture itself; root of the structural tree. |
| `Chapter` | `number` | `number`, `name` | Seed (name) + Extracted (number) | 18 | A chapter (adhyāya). Names are curated (not in verse files). |
| `Verse` | `id` (`"ch.verse"`) | `id`, `chapter`, `verse`, `translation`, `sanskrit`, `transliteration`, `embedding`, `embedding_model`, `embedding_revision`, `embedding_dimension`, `embedding_input_sha256` | Extracted + Computed | 701 | A single śloka. The atomic unit everything hangs off. |
| `Person` | `name` | `name`, `role`, `aliases` | Seed | 4 | The four framing voices of the dialogue: Krishna, Arjuna, Sanjaya, Dhritarashtra. |
| `Epithet` | `name` | `name` | Seed + Extracted | 22 | An honorific/title used for a person (e.g. Hrishikesha, Pārtha). |
| `Place` | `name` | `name` | Seed | 1 | The setting (Kurukshetra / Dharmakshetra). |
| `Term` | `lemma` | `lemma` | Extracted (spaCy) | 1171 | An English lemma from the translation. The statistical vocabulary layer. |
| `SanskritTerm` | `lemma` | `lemma` | Extracted (Word Meanings) | 3340 | A normalized Sanskrit word. The philological vocabulary layer. |
| `Theme` | `name` | `name`, `label`, `category` | Seed taxonomy → Derived edges | 13 | A broad topic cluster defined by a set of English lemmas. |
| `Concept` | `name` | `name`, `label`, `category` | Seed taxonomy → Derived edges | 22 | A philosophical category grounded in Sanskrit terms (the "operating principles" of the text: karma, dharma, ātman…). |
| `Character` | `name` | `name` | Extracted (glosses) + Seed | 18 | Anyone named in the narrative, discovered from Word Meanings. Every `Person` also carries this label (see decisions below). |
| `Conch` | `name` | `name`, `kind` | Extracted (glosses) | 6 | A named war-conch of Chapter 1 (Panchajanya, Devadatta…). |
| `Vibhuti` | `name` | `name`, `label`, `chapter` | Extracted (Ch.10 `asmi`) | 1 | The grouping of Krishna's explicit "I am…" divine-glory declarations. |

---

## Relationship catalog

Direction is `(domain)-[:TYPE]->(range)`.

| Type | Domain → Range | Properties | Provenance | Count | Meaning |
|------|----------------|-----------|------------|------:|---------|
| `HAS_CHAPTER` | Text → Chapter | none | Seed | 18 | Structural containment. |
| `HAS_VERSE` | Chapter → Verse | none | Extracted | 701 | Structural containment. |
| `NEXT` | Verse → Verse | none | Extracted | 683 | Reading order within a chapter. |
| `SPOKEN_BY` | Verse → Person | none | Extracted | 701 | Who speaks the verse (from the `"X said,"` prefix, inherited across runs). |
| `ADDRESSED_TO` | Verse → Person | none | Derived | 701 | Who the verse is addressed to (dialogue pairing). |
| `USES_EPITHET` | Verse → Epithet | none | Extracted | 32 | An honorific appears in the verse. |
| `EPITHET_OF` | Epithet → Person | none | Seed | 22 | Which person the honorific denotes. |
| `SET_IN` | Verse → Place | none | Seed | 1 | The setting reference. |
| `CHARIOTEER_OF` | Person → Person | none | Seed | 1 | Krishna is Arjuna's charioteer. |
| `NARRATES_TO` | Person → Person | none | Seed | 1 | Sanjaya narrates to Dhritarashtra. |
| `MENTIONS_TERM` | Verse → Term | `count` | Extracted | 6156 | English lemma occurs in the verse (with frequency). |
| `CONTAINS_TERM` | Verse → SanskritTerm | none | Extracted | 7995 | Sanskrit term occurs in the verse's Word Meanings. |
| `INCLUDES_TERM` | Theme → Term | none | Seed | 58 | The English lemmas that define a theme. |
| `MENTIONS_THEME` | Verse → Theme | `weight` | Derived | 1286 | Verse touches a theme; weight = summed term counts. |
| `INSTANCE_OF` | SanskritTerm → Concept | none | Derived | 139 | A Sanskrit term is an instance of a concept. |
| `EXPRESSES_CONCEPT` | Verse → Concept | `weight` | Derived | 841 | Verse expresses a concept; weight = distinct terms. |
| `ALIGNS_WITH` | Concept → Theme | none | Derived | 9 | A Sanskrit concept aligns with the English theme of the same name (the bridge between the two idea layers). |
| `MENTIONS_CHARACTER` | Verse → Character | none | Extracted | 310 | A character is named in the verse. |
| `NAMES_CONCH` | Verse → Conch | none | Extracted | 12 | A named conch appears in the verse. |
| `SOUNDS_CONCH` | Character → Conch | none | Extracted | 6 | The warrior who blows the conch (attested Ch.1 v15-16). |
| `DECLARES_VIBHUTI` | Verse → Vibhuti | none | Extracted | 13 | Verse is one of Krishna's "I am…" declarations. |
| `MANIFESTS_AS` | Character → Vibhuti | none | Extracted | 1 | Krishna is the one who manifests the glories. |
| `SIMILAR_TO` | Verse → Verse | `score`, `mutual`, `rank_a`, `rank_b`, `model`, `revision`, `top_k`, `threshold` | Computed | 2260 | Semantic similarity (undirected in meaning; stored on the canonical lower-id endpoint). Always query with `-[r:SIMILAR_TO]-`. |

---

## Layered view

```
Structure     Text → Chapter → Verse → (NEXT) → Verse
Dialogue      Verse → SPOKEN_BY / ADDRESSED_TO → Person ; Epithet ; Place
Vocabulary    Verse → MENTIONS_TERM → Term          (English, statistical)
              Verse → CONTAINS_TERM → SanskritTerm  (Sanskrit, philological)
Meaning       Verse → MENTIONS_THEME → Theme        (from English terms)
              Verse → EXPRESSES_CONCEPT → Concept    (from Sanskrit terms)
              Concept → ALIGNS_WITH → Theme          (shared-name bridge)
Narrative     Verse → MENTIONS_CHARACTER → Character → SOUNDS_CONCH → Conch
              Verse → DECLARES_VIBHUTI → Vibhuti ← MANIFESTS_AS ← Krishna
Semantics     Verse - SIMILAR_TO - Verse            (embeddings)
```

---

## Ontology decisions

Three label overlaps were identified and resolved.

### 1. `Person` vs `Character`: resolved, Person is a role marker
- **Every `Person` is now also a `Character`.** `Person` marks a structural role
  in the dialogue (speaker / addressee); `Character` marks a named entity in the
  story world. All 4 persons (including the narrator `Sanjaya`, who is never named
  inside a verse) carry both labels; 14 figures are `Character`-only.
- Query `MATCH (p:Person) WHERE NOT p:Character` now returns nothing.

### 2. `Theme` vs `Concept`: resolved, kept both and bridged
- `Theme` (13) = reader-facing topic index from **English** lemmas.
  `Concept` (22) = philosophical ontology grounded in **Sanskrit** terms.
- They are now linked by `(:Concept)-[:ALIGNS_WITH]->(:Theme)` on the 9 shared
  names (`atman`, `brahman`, `dharma`, `karma`, `yoga`, `bhakti`, `jnana`,
  `moksha`, `guna`). Each layer keeps its own provenance and granularity; the
  bridge lets a query cross between the English index and the Sanskrit ontology.

### 3. `Term` vs `SanskritTerm`: open (intentionally)
- Two parallel vocabularies (English lemma vs Sanskrit lemma), linked only via the
  shared `Verse`. Left unbridged for now; a future `TRANSLATES_TO` edge could join
  a Sanskrit term to its English gloss lemma if cross-language queries are needed.

---

## Coverage notes / honest limits

- **Character discovery is gazetteer-based**, so it is deliberately conservative.
  The Chapter 1 roster (including `Nakula`, `Drupada`, `Virata`) is covered; new
  named figures require adding a gazetteer stem in `PRINCIPALS`.
- **Vibhuti** is scoped to the explicit `asmi` ("I am") declarations of Ch.10 (13
  verses). It intentionally does **not** try to pair each glory with its class
  ("among X I am Y"), because Sanskrit word order there is inconsistent and
  automatic pairing would be unreliable.
- **Epithets and the setting** are curated seeds; they are not exhaustively
  mined from every verse.

---

## Example queries

```cypher
-- Full text is present (not a display artifact)
MATCH (v:Verse) RETURN count(v);                         -- 701

-- All of one chapter, in order
MATCH (v:Verse) WHERE v.chapter = 2 RETURN v ORDER BY v.verse;

-- The philosophical spine: verses most about a concept
MATCH (v:Verse)-[e:EXPRESSES_CONCEPT]->(c:Concept {name:'karma'})
RETURN v.id, e.weight ORDER BY e.weight DESC LIMIT 10;

-- Who sounds which conch
MATCH (c:Character)-[:SOUNDS_CONCH]->(k:Conch) RETURN c.name, k.name;

-- Semantic neighbours of a verse (undirected!)
MATCH (a:Verse {id:'2.47'})-[r:SIMILAR_TO]-(b:Verse)
RETURN b.id, r.score ORDER BY r.score DESC LIMIT 5;
```
