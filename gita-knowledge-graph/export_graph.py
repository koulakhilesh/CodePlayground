"""Export the Bhagavad Gita knowledge graph to a standalone interactive HTML.

Pulls the graph from Neo4j and renders it with Plotly (no Neo4j UI needed).
Defaults to the structural backbone (everything except the dense ``Term`` and
``SanskritTerm`` layers); pass ``--include-terms`` for the full graph.

    uv run python gita-knowledge-graph/export_graph.py
    uv run python gita-knowledge-graph/export_graph.py --include-terms
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path

import networkx as nx
import plotly.graph_objects as go
from dotenv import load_dotenv
from neo4j import GraphDatabase

_PKG = Path(__file__).resolve().parent
sys.path.insert(0, str(_PKG))
import gita_kg as gk  # noqa: E402

_LABEL_COLORS = {
    "Text": "#111111",
    "Chapter": "#1f77b4",
    "Verse": "#ff7f0e",
    "Person": "#2ca02c",
    "Epithet": "#d62728",
    "Place": "#9467bd",
    "Theme": "#e377c2",
    "Concept": "#17becf",
    "Character": "#bcbd22",
    "Conch": "#7f7f7f",
    "Vibhuti": "#e7ba52",
    "Term": "#8c564b",
    "SanskritTerm": "#c49c94",
}
_CAPTION_PROP = {
    "Text": "name", "Chapter": "name", "Verse": "id", "Person": "name",
    "Epithet": "name", "Place": "name", "Theme": "name", "Concept": "name",
    "Character": "name", "Conch": "name", "Vibhuti": "name",
    "Term": "lemma", "SanskritTerm": "lemma",
}


def _caption(label: str, props: dict) -> str:
    return str(props.get(_CAPTION_PROP.get(label, "name"), "?"))


def fetch_graph(driver, database: str, include_terms: bool) -> nx.DiGraph:
    where = "" if include_terms else (
        "WHERE NOT n:Term AND NOT m:Term "
        "AND NOT n:SanskritTerm AND NOT m:SanskritTerm "
    )
    query = (
        "MATCH (n)-[r]->(m) "
        f"{where}"
        "RETURN elementId(n) AS ns, labels(n) AS nl, properties(n) AS np, "
        "type(r) AS rt, "
        "elementId(m) AS ms, labels(m) AS ml, properties(m) AS mp"
    )
    g = nx.DiGraph()
    with driver.session(database=database) as session:
        for row in session.run(query):
            for eid, labels, props in (
                (row["ns"], row["nl"], row["np"]),
                (row["ms"], row["ml"], row["mp"]),
            ):
                label = labels[0]
                g.add_node(eid, label=label, caption=_caption(label, props))
            g.add_edge(row["ns"], row["ms"], rtype=row["rt"])
    return g


def build_figure(g: nx.DiGraph, title: str) -> go.Figure:
    pos = nx.spring_layout(g, k=0.15, iterations=50, seed=42)

    edge_x, edge_y = [], []
    for a, b in g.edges():
        edge_x += [pos[a][0], pos[b][0], None]
        edge_y += [pos[a][1], pos[b][1], None]
    edge_trace = go.Scatter(
        x=edge_x, y=edge_y, mode="lines", hoverinfo="none",
        line=dict(width=0.4, color="#cccccc"),
    )

    traces = [edge_trace]
    for label, color in _LABEL_COLORS.items():
        nodes = [n for n, d in g.nodes(data=True) if d["label"] == label]
        if not nodes:
            continue
        traces.append(
            go.Scatter(
                x=[pos[n][0] for n in nodes],
                y=[pos[n][1] for n in nodes],
                mode="markers",
                name=label,
                text=[g.nodes[n]["caption"] for n in nodes],
                hovertemplate=f"<b>{label}</b>: %{{text}}<extra></extra>",
                marker=dict(
                    size=7 if label in {"Verse", "Term", "SanskritTerm"} else 14,
                    color=color, line=dict(width=0.5, color="#ffffff"),
                ),
            )
        )

    fig = go.Figure(data=traces)
    fig.update_layout(
        title=title, showlegend=True, hovermode="closest",
        margin=dict(l=10, r=10, t=40, b=10),
        xaxis=dict(visible=False), yaxis=dict(visible=False),
    )
    return fig


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--include-terms", action="store_true",
                        help="include the dense Term and SanskritTerm layers (full graph)")
    args = parser.parse_args()

    load_dotenv(_PKG / ".env", override=True)
    cfg = gk.load_config()
    driver = GraphDatabase.driver(cfg.uri, auth=(cfg.user, cfg.password))
    try:
        g = fetch_graph(driver, cfg.database, args.include_terms)
    finally:
        driver.close()

    scope = "full" if args.include_terms else "backbone"
    title = f"Bhagavad Gita Knowledge Graph ({scope}): {g.number_of_nodes()} nodes, {g.number_of_edges()} edges"
    out = _PKG / "exports" / f"gita_graph_{scope}.html"
    out.parent.mkdir(exist_ok=True)
    build_figure(g, title).write_html(out, include_plotlyjs="cdn")
    print(f"wrote {out} ({g.number_of_nodes()} nodes, {g.number_of_edges()} edges)")


if __name__ == "__main__":
    main()
