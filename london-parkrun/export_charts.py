"""Export the Plotly charts and thumbnail for the two London parkrun posts.

Mirrors parkrun_access.ipynb / parkrun_shape.ipynb. Run from the repo root:
    python london-parkrun/export_charts.py
Then copy exports/*.html to koulakhilesh.github.io/assets/parkrun/.
"""
from __future__ import annotations

import sys
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
import plotly.express as px
import plotly.graph_objects as go

sys.path.insert(0, str(Path(__file__).resolve().parent))
import london_parkrun as lp  # noqa: E402

EXPORT_DIR = Path(__file__).resolve().parent / "exports"
VIEWPORT_META = '<meta name="viewport" content="width=device-width, initial-scale=1" />'
HTML_CONFIG = {"responsive": True, "displaylogo": False}
MAP_STYLE = "carto-positron"
FONT = dict(family="Inter, system-ui, sans-serif", size=13)
CENTRE = dict(lat=51.49, lon=-0.12)


def style(fig: go.Figure, title: str) -> go.Figure:
    fig.update_layout(title=dict(text=title, x=0.02), font=FONT, template="plotly_white",
                      autosize=True, margin=dict(l=60, r=20, t=60, b=50))
    return fig


def map_style(fig: go.Figure, title: str) -> go.Figure:
    style(fig, title)
    fig.update_layout(map=dict(style=MAP_STYLE, center=CENTRE, zoom=8.8), margin=dict(l=0, r=0, t=50, b=0))
    return fig


def write(fig: go.Figure, name: str) -> None:
    EXPORT_DIR.mkdir(exist_ok=True)
    html = fig.to_html(include_plotlyjs="cdn", full_html=True, config=HTML_CONFIG)
    (EXPORT_DIR / name).write_text(html.replace("<head>", f"<head>{VIEWPORT_META}", 1), encoding="utf-8")
    print("wrote", name)


def wgs(gdf):
    g = gdf.to_crs(lp.WGS84)
    return g.assign(lon=g.geometry.x, lat=g.geometry.y)


def load():
    boroughs = lp.load_boroughs()
    events = lp.filter_london_5k(lp.load_events(), boroughs)
    lsoa = lp.lsoa_access(lp.attach_ptal(lp.load_lsoa(), lp.load_lsoa11_ptal()), events)
    return boroughs, events, lsoa, lp.load_stations()


def fig_events_map(events, stations) -> go.Figure:
    sa = lp.station_access(events, stations)
    sa["walk"] = (sa["station_m"] <= 1000).map({True: "≤ 1 km from a station", False: "> 1 km from a station"})
    sa["km"] = (sa["station_m"] / 1000).round(2)
    pts = wgs(sa)
    fig = px.scatter_map(pts, lat="lat", lon="lon", color="walk", hover_name="short_name",
                         hover_data={"station": True, "km": True, "lat": False, "lon": False, "walk": False},
                         color_discrete_map={"> 1 km from a station": "#1f4e9c", "≤ 1 km from a station": "#c8102e"})
    fig.update_traces(marker=dict(size=11))
    return map_style(fig, "London's 5k parkruns and the nearest station")


def fig_distance_map(lsoa) -> go.Figure:
    pts = wgs(lp.centroids(lsoa).join(lsoa[["lsoa21nm", "nearest_event", "dist_m"]]))
    pts["km"] = (pts["dist_m"] / 1000).round(2)
    fig = px.scatter_map(pts, lat="lat", lon="lon", color="km", hover_name="lsoa21nm",
                         hover_data={"nearest_event": True, "km": True, "lat": False, "lon": False},
                         color_continuous_scale="Viridis_r", range_color=(0, 4))
    fig.update_traces(marker=dict(size=4))
    return map_style(fig, "Straight-line distance to the nearest parkrun (km)")


def fig_coverage(lsoa) -> go.Figure:
    cov = lp.coverage_by_threshold(lsoa)
    cov["label"] = (cov["threshold_m"] // 1000).astype(str) + " km"
    cov["pct"] = (100 * cov["share"]).round(1)
    fig = px.bar(cov, x="label", y="pct", text="pct")
    fig.update_traces(texttemplate="%{text}%", marker_color="#1f4e9c")
    fig.update_yaxes(title="% of Londoners", range=[0, 100])
    fig.update_xaxes(title="Lives within")
    return style(fig, "Londoners within a straight-line distance of a parkrun")


def fig_boroughs(lsoa) -> go.Figure:
    b = lp.borough_access(lsoa).sort_values("median_dist_m")
    b["km"] = (b["median_dist_m"] / 1000).round(2)
    fig = px.bar(b, x="km", y="borough", orientation="h", hover_data={"population": True})
    fig.update_traces(marker_color="#1f4e9c")
    fig.update_xaxes(title="Median distance to nearest parkrun (km, population-weighted)")
    fig.update_yaxes(title=None)
    return style(fig, "Median distance to a parkrun, by borough")


def fig_car_free_gap(lsoa) -> go.Figure:
    gap = lp.car_free_gap(lsoa)
    pts = wgs(lp.centroids(gap).join(gap[["lsoa21nm", "borough", "dist_m", "no_car_share", "ptal", "gap", "low_ptal"]]))
    pts = pts[pts["gap"]].copy()
    pts["group"] = pts["low_ptal"].map({True: "…and low PTAL (0–2)", False: "PTAL 3+"})
    pts["km"] = (pts["dist_m"] / 1000).round(2)
    pts["no car %"] = (100 * pts["no_car_share"]).round(0)
    fig = px.scatter_map(pts, lat="lat", lon="lon", color="group", hover_name="lsoa21nm",
                         hover_data={"borough": True, "km": True, "no car %": True, "ptal": True,
                                     "lat": False, "lon": False, "group": False},
                         color_discrete_map={"…and low PTAL (0–2)": "#c8102e", "PTAL 3+": "#f2a900"})
    fig.update_traces(marker=dict(size=6))
    return map_style(fig, "Over 2 km from a parkrun, in low-car areas")


def fig_catchments(lsoa, events) -> go.Figure:
    cat = lp.catchments(lsoa, events).sort_values("population")
    fig = px.bar(cat, x="population", y="short_name", orientation="h", hover_data={"lsoas": True})
    fig.update_traces(marker_color="#1f4e9c")
    fig.update_xaxes(title="Residents whose nearest parkrun this is")
    fig.update_yaxes(title=None)
    fig.update_layout(height=1100)
    return style(fig, "Who lives closest to each parkrun")


def thumbnail(boroughs, events) -> None:
    fig, ax = plt.subplots(figsize=(6.4, 6.4), dpi=100)
    boroughs.boundary.plot(ax=ax, color="#9aa3ad", linewidth=0.5)
    events.buffer(2000).plot(ax=ax, color="#1f4e9c", alpha=0.18, linewidth=0)
    events.plot(ax=ax, color="#c8102e", markersize=14)
    ax.set_axis_off()
    fig.subplots_adjust(0, 0, 1, 1)
    EXPORT_DIR.mkdir(exist_ok=True)
    fig.savefig(EXPORT_DIR / "parkrun-thumb.png", facecolor="white")
    plt.close(fig)
    print("wrote parkrun-thumb.png")


def fig_id_map(events) -> go.Figure:
    pts = wgs(events)
    pts["order"] = pts["id"].rank().astype(int)
    fig = px.scatter_map(pts, lat="lat", lon="lon", color="order", hover_name="short_name",
                         hover_data={"id": True, "order": True, "lat": False, "lon": False},
                         color_continuous_scale="Plasma")
    fig.update_traces(marker=dict(size=11))
    return map_style(fig, "London parkruns by launch order (event ID)")


def fig_names(events) -> go.Figure:
    t = lp.name_terms(events).rename_axis("term").reset_index(name="events").sort_values("events")
    fig = px.bar(t, x="events", y="term", orientation="h")
    fig.update_traces(marker_color="#1f4e9c")
    fig.update_yaxes(title=None)
    return style(fig, "What London's parkruns are named after")


def fig_extremes(events) -> go.Figure:
    x = lp.event_extremes(events)
    pts = wgs(events)
    pts["role"] = "parkrun"
    pts.loc[pts["short_name"] == x["most_isolated"], "role"] = "most isolated"
    pts.loc[pts["short_name"].isin(x["closest_pair"]), "role"] = "closest pair"
    fig = px.scatter_map(pts, lat="lat", lon="lon", color="role", hover_name="short_name",
                         hover_data={"lat": False, "lon": False, "role": False},
                         color_discrete_map={"parkrun": "#9aa3ad", "most isolated": "#c8102e", "closest pair": "#1f4e9c"})
    fig.update_traces(marker=dict(size=11))
    return map_style(fig, "The loneliest parkrun and the closest pair")


def fig_alphabet(events) -> go.Figure:
    route = lp.alphabet_route(events)
    pts = wgs(events).set_index("short_name").loc[route].reset_index()
    pts["letter"] = [lp.first_letter(n) for n in pts["short_name"]]
    fig = go.Figure(go.Scattermap(lat=pts["lat"], lon=pts["lon"], mode="lines+markers+text",
                                  text=pts["letter"], textposition="top right", hovertext=pts["short_name"],
                                  line=dict(color="#c8102e", width=2), marker=dict(size=9, color="#1f4e9c")))
    return map_style(fig, f"One parkrun per letter: {len(route)} letters, {lp.path_length(events, route) / 1000:.0f} km")


def fig_next(events, lsoa, boroughs) -> go.Figure:
    picks = wgs(lp.best_new_sites(lp.candidate_sites(lp.load_greenspace(boroughs), boroughs, events), lsoa))
    ev = wgs(events)
    far = wgs(lp.centroids(lsoa[lsoa["dist_m"] > 2000]))
    fig = go.Figure()
    fig.add_trace(go.Scattermap(lat=far["lat"], lon=far["lon"], mode="markers", name="> 2 km from a parkrun",
                                marker=dict(size=4, color="#f2a900"), hoverinfo="skip"))
    fig.add_trace(go.Scattermap(lat=ev["lat"], lon=ev["lon"], mode="markers", name="existing parkrun",
                                marker=dict(size=9, color="#1f4e9c"), hovertext=ev["short_name"]))
    fig.add_trace(go.Scattermap(lat=picks["lat"], lon=picks["lon"], mode="markers+text", name="suggested site",
                                text=[str(i + 1) for i in range(len(picks))], textposition="top right",
                                marker=dict(size=14, color="#c8102e"),
                                hovertext=[f"{s}: +{int(p):,} people" for s, p in zip(picks["site"], picks["added_population"])]))
    return map_style(fig, "Five more parkruns: sites that bring most people within 2 km")


def main() -> None:
    boroughs, events, lsoa, stations = load()
    write(fig_events_map(events, stations), "events-map.html")
    write(fig_distance_map(lsoa), "distance-map.html")
    write(fig_coverage(lsoa), "coverage.html")
    write(fig_boroughs(lsoa), "boroughs.html")
    write(fig_car_free_gap(lsoa), "car-free-gap.html")
    write(fig_catchments(lsoa, events), "catchments.html")
    write(fig_id_map(events), "id-map.html")
    write(fig_names(events), "names.html")
    write(fig_extremes(events), "extremes.html")
    write(fig_alphabet(events), "alphabet-route.html")
    write(fig_next(events, lsoa, boroughs), "next-parkrun.html")
    thumbnail(boroughs, events)


if __name__ == "__main__":
    main()
