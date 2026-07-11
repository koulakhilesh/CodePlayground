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

## License

Released under the [MIT License](LICENSE).
