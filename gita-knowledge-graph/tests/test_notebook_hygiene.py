import json
from pathlib import Path


PROJECT_ROOT = Path(__file__).parents[1]


def notebook_source(path: Path) -> str:
    notebook = json.loads(path.read_text())
    return "\n".join(
        line
        for cell in notebook["cells"]
        for line in cell.get("source", [])
    )


def test_published_docs_do_not_reference_internal_specs():
    sources = {
        path.name: notebook_source(path)
        for path in PROJECT_ROOT.glob("*.ipynb")
    }
    sources["README.md"] = (PROJECT_ROOT / "README.md").read_text()

    for name, source in sources.items():
        assert "docs/superpowers/specs/" not in source, name
        assert "**Spec:**" not in source, name


def test_vector_examples_use_search_clause():
    notebook = notebook_source(PROJECT_ROOT / "similarity_kg.ipynb")
    readme = (PROJECT_ROOT / "README.md").read_text()

    for source in (notebook, readme):
        assert "db.index.vector.queryNodes" not in source
        assert "SEARCH node IN (" in source