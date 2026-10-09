# CodePlayground

A personal playground for data science, machine learning, and coding experiments:
notebooks, small scripts, and things I'm learning along the way.

## Contents

Each experiment lives in its own folder, with shared data under `data/`:

- [`london-reservoir-levels/`](london-reservoir-levels/): 37 years of daily London
  reservoir levels, explored and visualised with Plotly.
- [`london-blue-plaques/`](london-blue-plaques/): a scraper for every English Heritage
  London blue plaque, an analysis notebook (who gets remembered, and where), and a
  geospatial/optimisation notebook (Voronoi, DBSCAN, minimum spanning tree, and a
  hand-rolled travelling-salesman tour).
- [`london_tube_crowding/`](london_tube_crowding/): a London Tube movement EDA project
  that fetches live station metadata, extracts NaPTAN codes, and flattens TfL crowding
  time-series data for exploratory analysis.
- [`gita-knowledge-graph/`](gita-knowledge-graph/): a Sanskrit-grounded knowledge
  graph of the Bhagavad Gita in Neo4j — 701 verses linked to themes, concepts, the
  character cast, and semantic similarity, all built by a single notebook. The
  domain model is documented in [ONTOLOGY.md](gita-knowledge-graph/ONTOLOGY.md).
- [`london-wren-churches/`](london-wren-churches/): an evidence-tiered research
  pipeline on Wren's post-Great-Fire City churches: rebuilding intervals, how and why
  churches were lost, the 34 parishes never rebuilt, relocated fabric, a discovery
  graph and published visitor listings. Every claim carries its source and review
  status; see [METHODS.md](london-wren-churches/METHODS.md).

## Getting started

This project uses [uv](https://docs.astral.sh/uv/) for Python environment and
package management.

```bash
git clone git@github.com:koulakhilesh/CodePlayground.git
cd CodePlayground

# create the virtual environment and install dependencies from the lockfile
uv sync

# launch Jupyter
uv run jupyter notebook

# add / remove a dependency
uv add <package>
uv remove <package>
```

`uv` reads the target Python version from `.python-version` and pins exact
dependency versions in `uv.lock`.

## Tests

Projects with a `tests/` suite are tested with `pytest`:

```bash
uv run pytest gita-knowledge-graph -m "not integration"   # unit tests, no Neo4j/model
uv run pytest london-blue-plaques
uv run pytest london-wren-churches
```

GitHub Actions ([`.github/workflows/tests.yml`](.github/workflows/tests.yml)) runs
these per project on every pull request and on pushes to `main`. Integration tests
(which need the sentence-transformer model or a live Neo4j) are skipped in CI.

## License

Released under the [MIT License](LICENSE).
