"""Export the Plotly charts and thumbnail for the two Wren website posts.

Run from the repo root after the pipeline (review, analyse, discover, walk):
    python london-wren-churches/export_wren_charts.py
Then copy exports/site/*.html to koulakhilesh.github.io/assets/wren/ and
exports/site/wren-thumb.png to assets/thumbs/wren.png.

Every chart carries the source line from SOURCES; the full source list is in README.md.
"""
from __future__ import annotations

import json
from pathlib import Path
import re
from textwrap import wrap

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import plotly.graph_objects as go
from pyproj import Geod, Transformer

HERE = Path(__file__).resolve().parent
DATA = HERE.parent / "data" / "london_wren_churches"
EXPORTS = HERE / "exports"
OUT = EXPORTS / "site"
VIEWPORT_META = '<meta name="viewport" content="width=device-width, initial-scale=1" />'
HTML_CONFIG = {"responsive": True, "displaylogo": False}
FONT = dict(family="Inter, system-ui, sans-serif", size=13)
RED, BLUE, YELLOW, GREY = "#c8102e", "#1f4e9c", "#f2a900", "#9aa3ad"
CENTRE = dict(lat=51.5125, lon=-0.095)
FATE_COLOURS = {"standing": BLUE, "tower only": YELLOW, "gone": RED, "related site": GREY}
STANDING = {"Survived in original form", "Substantially rebuilt after the Blitz", "Substantially altered before the Blitz",
            "Interior refurbished by Christopher Wren", "Churches built outside the City of London"}
TIER_COLOURS = {"verified": BLUE, "agreeing_sources": "#6b8fc9", "disputed": RED, "reported": GREY}
TIER_LABELS = {"verified": "verified", "agreeing_sources": "two sources agree", "disputed": "disputed",
               "reported": "one list only"}
STATUS_LABELS = {"hours_published": "hours published", "closure_notice": "closed or closing",
                 "by_arrangement": "by arrangement", "no_regular_hours": "no regular hours",
                 "services_only": "services only", "no_hours_listed": "no hours listed"}
GRID_LETTERS = "ABCDEFGHJKLMNOPQRSTUVWXYZ"
GEOD = Geod(ellps="WGS84")
WIKI = "Wikipedia (CC BY-SA 4.0)"
HE = "Historic England list entries (OGL v3.0)"
SOURCES = {
    "fate-map.html": f"Data: List of Christopher Wren churches in London and church articles, {WIKI}; {HE}.",
    "rebuilding.html": f"Data: church articles, {WIKI}; {HE}; Parentalia (1750), Internet Archive scan.",
    "costs.html": f"Data: church articles, {WIKI}. Pounds as stated, not inflation-adjusted.",
    "losses.html": f"Data: Wren church list and articles; census table in the City of London article, {WIKI}.",
    "relocations.html": f"Data: Historic England list entries 1080836 and 1079973 (OGL v3.0); City sites from {WIKI}.",
    "parish-unions.html": f"Data: List of churches destroyed in the Great Fire of London and not rebuilt, {WIKI}.",
    "visiting-map.html": f"Data: Friends of the City Churches and official church websites, as published on the date in the hover; sites from {WIKI}.",
}


def grid_to_lonlat(reference: str) -> tuple[float, float]:
    """OSGB grid reference such as 'TQ 35072 72545' to WGS84 (lon, lat)."""
    letters, east, north = re.fullmatch(r"([A-Z]{2})\s*(\d{5})\s*(\d{5})", reference.strip()).groups()
    first, second = (GRID_LETTERS.index(char) for char in letters)
    e100 = ((first - 2) % 5) * 5 + second % 5
    n100 = 19 - (first // 5) * 5 - second // 5
    transformer = Transformer.from_crs("EPSG:27700", "EPSG:4326", always_xy=True)
    return transformer.transform(e100 * 100000 + int(east), n100 * 100000 + int(north))


def fate(section: str | None, cohort: str, lost: bool) -> str:
    if section == "Tower remaining":
        return "tower only"
    if section in STANDING and not lost:
        return "standing"
    if cohort == "cathedral":
        return "standing"
    return "gone"


def style(fig: go.Figure, title: str, height: int | None = None) -> go.Figure:
    fig.update_layout(title=dict(text=title, x=0.02), font=FONT, template="plotly_white", autosize=True,
                      margin=dict(l=60, r=20, t=60, b=50), legend=dict(orientation="h", y=-0.12))
    if height:
        fig.update_layout(height=height)
    return fig


def top_legend(fig: go.Figure, height: int, top: int) -> go.Figure:
    # Container coordinates keep the legend under the title however many rows it wraps to.
    fig.update_layout(title=dict(y=1, yref="container", yanchor="top", pad=dict(t=14)),
                      legend=dict(orientation="h", yref="container", y=1 - 48 / height, yanchor="top", x=0),
                      margin=dict(l=10, r=20, t=top, b=50))
    return fig


def map_style(fig: go.Figure, title: str, zoom: float = 13.2, centre: dict | None = None) -> go.Figure:
    style(fig, title)
    fig.update_layout(map=dict(style="carto-positron", center=centre or CENTRE, zoom=zoom),
                      margin=dict(l=0, r=0, t=50, b=0), legend=dict(orientation="h", y=0.01, x=0.01,
                                                                    bgcolor="rgba(255,255,255,0.85)"))
    return fig


def cite(fig: go.Figure, text: str, width: int = 58) -> go.Figure:
    # Pre-wrapped for a 350px phone frame; right-anchored because long category labels shift the plot's left edge.
    lines = wrap(text, width)
    bottom = (fig.layout.margin.b or 0) + 14 * len(lines) + 10
    fig.add_annotation(text="<br>".join(lines), xref="paper", x=1, xanchor="right", yref="paper", y=0,
                       yanchor="bottom", yshift=4 - bottom, showarrow=False, align="right",
                       font=dict(size=10, color="#5f6670"))
    fig.update_layout(margin=dict(b=bottom))
    return fig


def write(fig: go.Figure, name: str) -> None:
    cite(fig, SOURCES[name])
    OUT.mkdir(parents=True, exist_ok=True)
    html = fig.to_html(include_plotlyjs="cdn", full_html=True, config=HTML_CONFIG)
    (OUT / name).write_text(html.replace("<head>", f"<head>{VIEWPORT_META}", 1), encoding="utf-8")
    print("wrote", name)


def load() -> dict:
    tables = json.loads((DATA / "tables_reviewed.json").read_text())
    summary = json.loads((EXPORTS / "analysis_summary.json").read_text())
    return {"tables": tables, "tiered": summary["tiered"],
            "points": json.loads((EXPORTS / "map_points.json").read_text()),
            "graph": json.loads((EXPORTS / "discovery.json").read_text())}


def church_sites(data: dict) -> list[dict]:
    tables, tiered = data["tables"], data["tiered"]
    sections = {c["subject_id"]: c["value"] for c in tables["claims"] if c["field"] == "seed_section"}
    lost_body = {row["church_id"] for row in tiered["losses"] if row["kind"] in {"demolition", "destruction"}}
    restored = {e["church_id"] for e in tables["events"] if e["kind"] in {"restoration", "rebuilding"}}
    lost_body -= restored
    cohorts = {c["church_id"]: c["cohort"] for c in tables["churches"]}
    seen, rows = set(), []
    for point in data["points"]:
        identifier = point.get("church_id")
        if identifier in seen:
            continue
        if identifier is None:
            rows.append(dict(point, fate="related site", section="Related site"))
            continue
        seen.add(identifier)
        section = sections.get(identifier)
        rows.append(dict(point, section=section or "not listed",
                         fate=fate(section, cohorts[identifier], identifier in lost_body)))
    return rows


def fig_fate_map(data: dict) -> go.Figure:
    rows = church_sites(data)
    built = {r["church_id"]: f"Built {r['earliest_year']}-{r['latest_year']} ({TIER_LABELS[r['evidence_tier']]})"
             for r in data["tiered"]["construction"] if r["earliest_year"] and r["latest_year"]}
    fig = go.Figure()
    for label, colour in FATE_COLOURS.items():
        sel = [r for r in rows if r["fate"] == label]
        fig.add_trace(go.Scattermap(lat=[r["latitude"] for r in sel], lon=[r["longitude"] for r in sel],
                                    mode="markers", name=f"{label} ({len(sel)})",
                                    marker=dict(size=11 if label != "related site" else 9, color=colour),
                                    text=[r["name"] for r in sel],
                                    customdata=[[r["section"], built.get(r.get("church_id"), "")] for r in sel],
                                    hovertemplate="<b>%{text}</b><br>%{customdata[0]}<br>%{customdata[1]}<extra></extra>"))
    return map_style(fig, "Wren's City churches today", zoom=13.4)


def fig_rebuilding(data: dict) -> go.Figure:
    rows = sorted(data["tiered"]["construction"], key=lambda r: (r["earliest_year"] or 9999, r["latest_year"] or 9999),
                  reverse=True)
    fig = go.Figure()
    order = [r["name"] for r in rows]
    for tier, colour in TIER_COLOURS.items():
        sel = [r for r in rows if r["evidence_tier"] == tier]
        fig.add_trace(go.Bar(y=[r["name"] for r in sel], base=[r["earliest_year"] for r in sel],
                             x=[max(r["latest_year"] - r["earliest_year"], 0.4) for r in sel], orientation="h",
                             marker_color=colour, name=TIER_LABELS[tier],
                             customdata=[[r["earliest_year"], r["latest_year"],
                                          "; ".join("-".join(str(v or "?") for v in alt) for alt in r["alternatives"]) or "none"]
                                         for r in sel],
                             hovertemplate="<b>%{y}</b><br>%{customdata[0]}-%{customdata[1]}<br>Other ranges: %{customdata[2]}<extra>%{fullData.name}</extra>"))
    marks = [r for r in rows if r.get("parentalia_year")]
    fig.add_trace(go.Scatter(y=[r["name"] for r in marks], x=[r["parentalia_year"] for r in marks], mode="markers",
                             name="1750 catalogue year", marker=dict(symbol="line-ns-open", size=14, color="#171410", line=dict(width=2)),
                             hovertemplate="<b>%{y}</b><br>Parentalia (1750): %{x}<extra></extra>"))
    style(fig, "Rebuilding intervals, by evidence", height=1080)
    fig.update_layout(barmode="overlay", xaxis=dict(title="Year", range=[1668, 1700], dtick=5),
                      yaxis=dict(categoryorder="array", categoryarray=order, automargin=True, tickfont=dict(size=11)))
    return top_legend(fig, 1080, 140)


def fig_costs(data: dict) -> go.Figure:
    rows = sorted((r for r in data["tiered"]["costs"] if r["cohort"] == "parish_replacement"), key=lambda r: r["decimal_pounds"])
    scope_label = {"rebuilding": "scope not split", "church": "church only", "church_and_tower": "church and tower",
                   "church_and_steeple": "church and steeple"}
    colours = {"scope not split": GREY, "church only": BLUE, "church and tower": YELLOW, "church and steeple": RED}
    fig = go.Figure()
    for label, colour in colours.items():
        sel = [r for r in rows if scope_label.get(r["scope"]) == label]
        if sel:
            fig.add_trace(go.Bar(x=[r["decimal_pounds"] for r in sel], y=[r["name"] for r in sel], orientation="h",
                                 marker_color=colour, name=label,
                                 customdata=[[r.get("note") or ""] for r in sel],
                                 hovertemplate="<b>%{y}</b><br>£%{x:,.0f}<br>%{customdata[0]}<extra>%{fullData.name}</extra>"))
    style(fig, "What 28 churches cost (£ at the time)", height=820)
    fig.update_layout(barmode="overlay", xaxis=dict(title="£ (nominal)", tickprefix="£", separatethousands=True),
                      yaxis=dict(categoryorder="array", categoryarray=[r["name"] for r in rows], automargin=True,
                                 tickfont=dict(size=11)))
    return top_legend(fig, 820, 120)


def spread(row: int, years: list[int], gap: int = 5) -> list[float]:
    """Vertical offsets around `row` so markers within `gap` years of the previous one don't hide each other."""
    out, step, last = [], 0, None
    for year in years:
        step = step + 1 if last is not None and year - last < gap else 0
        out.append(row + (0, 0.24, -0.24, 0.12, -0.12)[step % 5])
        last = year
    return out


def fig_losses(data: dict) -> go.Figure:
    tiered = data["tiered"]
    labels = {"site_clearance_or_street_works": "street works", "union_of_benefices": "Union of Benefices",
              "structural_safety": "found unsafe", "war_destruction": "Blitz", "war_ruins_cleared": "bombed ruins cleared"}
    colours = {"street works": BLUE, "Union of Benefices": RED, "found unsafe": YELLOW,
               "Blitz": "#171410", "bombed ruins cleared": GREY}
    fig = go.Figure()
    census = [r for r in tiered["population"] if r["count_type"] == "census" and r["year"] <= 1971]
    fig.add_trace(go.Scatter(x=[r["year"] for r in census], y=[r["population"] for r in census], mode="lines+markers",
                             name="City residents (census)", yaxis="y2", line=dict(color=GREY, width=2), marker=dict(size=5),
                             hovertemplate="%{x}: %{y:,} residents<extra></extra>"))
    for row, (mechanism, label) in enumerate(labels.items()):
        sel = sorted((r for r in tiered["losses"] if r["mechanism"] == mechanism and r["earliest_year"]),
                     key=lambda r: r["earliest_year"])
        fig.add_trace(go.Scatter(x=[r["earliest_year"] for r in sel], y=spread(row, [r["earliest_year"] for r in sel]),
                                 mode="markers", name=label,
                                 marker=dict(size=13, color=colours[label], line=dict(width=1, color="white")),
                                 text=[f"{r['name']} ({r['kind'].replace('_', ' ')})" for r in sel],
                                 hovertemplate="%{text}<br>%{x}<extra></extra>", showlegend=False))
    style(fig, "Losses and the City's population", height=520)
    fig.update_layout(xaxis=dict(title="Year", range=[1770, 1975]),
                      yaxis=dict(automargin=True, tickvals=list(range(len(labels))), ticktext=list(labels.values()),
                                 range=[-0.6, len(labels) - 0.4], zeroline=False),
                      yaxis2=dict(overlaying="y", side="right", showgrid=False, rangemode="tozero",
                                  separatethousands=True, automargin=True))
    return top_legend(fig, 520, 90)


def relocation_points(data: dict) -> list[dict]:
    claims = {c["claim_id"]: c for c in data["tables"]["claims"]}
    grids = {"church_ce1ae257c8d26b67fe2c": "claim_8cefbb9922a7bc558d7f", "church_9276dbe5911bb7c95486": "claim_3b0867b83b6d27f74ca2"}
    origins = {r["church_id"]: r for r in church_sites(data) if r.get("church_id")}
    rows = []
    for move in data["graph"]["relocations"]:
        if move["evidence_tier"] != "verified" or move["church_id"] not in grids:
            continue
        reference = re.search(r"National Grid Reference: ([A-Z]{2} \d{5} \d{5})", claims[grids[move["church_id"]]]["value"]["text"])[1]
        lon, lat = grid_to_lonlat(reference)
        origin = origins[move["church_id"]]
        metres = GEOD.inv(origin["longitude"], origin["latitude"], lon, lat)[2]
        rows.append({"name": move["name"], "destination": move["destination"], "year": move["earliest_year"],
                     "component": move["component"].replace("_", " "), "from": (origin["latitude"], origin["longitude"]),
                     "to": (lat, lon), "grid": reference, "distance_km": round(metres / 1000, 1)})
    return rows


def fig_relocations(data: dict) -> go.Figure:
    fig = go.Figure()
    for index, row in enumerate(relocation_points(data)):
        colour = [RED, BLUE][index % 2]
        fig.add_trace(go.Scattermap(lat=[row["from"][0], row["to"][0]], lon=[row["from"][1], row["to"][1]],
                                    mode="lines+markers", line=dict(color=colour, width=3), marker=dict(size=[9, 14], color=colour),
                                    name=f"{row['name']}: {row['component']}",
                                    text=[f"{row['name']} (City site)",
                                          f"{row['destination']}, {row['year']}<br>{row['distance_km']} km in a straight line"],
                                    hovertemplate="%{text}<extra></extra>"))
    return map_style(fig, "Wren fabric that moved", zoom=9.9, centre=dict(lat=51.475, lon=-0.18))


def fig_parish_unions(data: dict) -> go.Figure:
    rows = sorted(data["graph"]["parish_unions"], key=lambda r: (len(r["parishes"]), r["name"]))
    fig = go.Figure(go.Bar(x=[len(r["parishes"]) for r in rows], y=[r["name"] for r in rows], orientation="h",
                           marker_color=YELLOW, customdata=[[", ".join(p["name"] for p in r["parishes"])] for r in rows],
                           hovertemplate="<b>%{y}</b><br>Took in: %{customdata[0]}<extra></extra>"))
    style(fig, "Lost parishes taken in", height=760)
    fig.update_layout(xaxis=dict(title="Lost parishes united with this church", dtick=1),
                      yaxis=dict(automargin=True, tickfont=dict(size=11)), margin=dict(l=10, r=20, t=60, b=50), showlegend=False)
    return fig


def fig_visiting(data: dict) -> go.Figure:
    access = {row["church_id"]: row for row in data["tiered"]["visitor_access"]}
    sites = [r for r in church_sites(data) if r.get("church_id") in access]
    groups = {"open with published hours": BLUE, "restricted or closed": RED, "tower, garden or remains": YELLOW}

    def group(row: dict) -> str:
        info = access[row["church_id"]]
        if info["access_scope"] != "interior":
            return "tower, garden or remains"
        return "open with published hours" if info["published_status"] == "hours_published" else "restricted or closed"

    fig = go.Figure()
    for label, colour in groups.items():
        sel = [r for r in sites if group(r) == label]
        fig.add_trace(go.Scattermap(lat=[r["latitude"] for r in sel], lon=[r["longitude"] for r in sel], mode="markers",
                                    name=f"{label} ({len(sel)})", marker=dict(size=12, color=colour),
                                    text=[r["name"] for r in sel],
                                    customdata=[[STATUS_LABELS.get(access[r["church_id"]]["published_status"], ""),
                                                 access[r["church_id"]]["access_scope"].replace("_", " "),
                                                 access[r["church_id"]]["checked_at"]] for r in sel],
                                    hovertemplate="<b>%{text}</b><br>%{customdata[1]}: %{customdata[0]}<br>as published, checked %{customdata[2]}<extra></extra>"))
    return map_style(fig, "Published visiting information", zoom=13.2)


def thumbnail(data: dict) -> None:
    rows = [r for r in church_sites(data) if r["fate"] != "related site" and abs(r["longitude"] + 0.095) < 0.03]
    fig, ax = plt.subplots(figsize=(6.4, 6.4), dpi=100)
    for label, colour in (("gone", RED), ("tower only", YELLOW), ("standing", BLUE)):
        sel = [r for r in rows if r["fate"] == label]
        ax.scatter([r["longitude"] for r in sel], [r["latitude"] for r in sel], s=90, color=colour, edgecolor="white", linewidth=0.8)
    ax.set_aspect(1 / 0.62)
    ax.set_axis_off()
    fig.subplots_adjust(0, 0, 1, 1)
    OUT.mkdir(parents=True, exist_ok=True)
    fig.savefig(OUT / "wren-thumb.png", facecolor="white")
    plt.close(fig)
    print("wrote wren-thumb.png")


def main() -> None:
    data = load()
    write(fig_fate_map(data), "fate-map.html")
    write(fig_rebuilding(data), "rebuilding.html")
    write(fig_costs(data), "costs.html")
    write(fig_losses(data), "losses.html")
    write(fig_relocations(data), "relocations.html")
    write(fig_parish_unions(data), "parish-unions.html")
    write(fig_visiting(data), "visiting-map.html")
    thumbnail(data)


if __name__ == "__main__":
    main()
