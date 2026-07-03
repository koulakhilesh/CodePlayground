# CodePlayground

A personal playground for data science, machine learning, and coding experiments —
notebooks, small scripts, and things I'm learning along the way.

## Contents

Experiments live at the top level (Jupyter notebooks, scripts) with any
supporting data under `data/`.

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
