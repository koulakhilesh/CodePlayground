"""Generate post thumbnails as snapshots of the actual Plotly figures.

Recreates each post's signature figure and exports a PNG via kaleido, so the
thumbnail's colours match the interactive chart embedded in the post.

Requires kaleido (which downloads a Chrome-for-Testing on first use):
    python scripts/make_thumbnails.py [--out DIR]
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
import plotly.express as px
import plotly.io as pio
import shapely
from shapely.geometry import MultiPoint
from shapely.ops import voronoi_diagram

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data"
SIZE = 640

pio.templates.default = "plotly_white"


def _plaques() -> pd.DataFrame:
    df = pd.read_csv(DATA / "blue_plaques_2026-07.csv").dropna(subset=["lat", "lng"])
    df["category_main"] = df["category"].astype(str).str.split(",").str[0].str.strip()
    return df


def blue_plaques(out: Path, df: pd.DataFrame) -> None:
    top = df["category_main"].value_counts().head(10).index
    df = df.assign(cat=df["category_main"].where(df["category_main"].isin(top), "Other"))
    center = {"lat": df["lat"].mean(), "lon": df["lng"].mean()}
    fig = px.scatter_map(df, lat="lat", lon="lng", color="cat", zoom=9.7, center=center,
                         color_discrete_sequence=px.colors.qualitative.Safe)
    fig.update_traces(marker={"size": 6})
    fig.update_layout(map_style="carto-positron", showlegend=False,
                      margin={"r": 0, "t": 0, "l": 0, "b": 0})
    fig.write_image(out / "blue-plaques.png", width=SIZE, height=SIZE)
    print("wrote blue-plaques.png")


def geometry(out: Path, df: pd.DataFrame) -> None:
    pts = gpd.GeoDataFrame(df, geometry=gpd.points_from_xy(df["lng"], df["lat"]),
                           crs=4326).to_crs(27700)
    X = np.c_[pts.geometry.x.values, pts.geometry.y.values]
    mp = MultiPoint(list(map(tuple, X)))
    env = mp.convex_hull.buffer(600, quad_segs=1)
    cells = [g.intersection(env) for g in voronoi_diagram(mp, envelope=env).geoms]
    g = gpd.GeoDataFrame(geometry=cells, crs=27700)
    g["geometry"] = g.simplify(120)
    g["area_km2"] = g.area / 1e6
    c4 = g.to_crs(4326).reset_index(drop=True)
    c4["geometry"] = c4.geometry.apply(lambda geom: shapely.transform(geom, lambda a: np.round(a, 5)))
    c4 = c4[~c4.geometry.is_empty]
    c4["log_area"] = np.log10(c4["area_km2"].clip(lower=1e-3))
    center = {"lat": df["lat"].mean(), "lon": df["lng"].mean()}
    fig = px.choropleth_map(c4, geojson=json.loads(c4.to_json()), locations=c4.index,
                            color="log_area", color_continuous_scale="Blues_r", opacity=0.6,
                            map_style="carto-positron", center=center, zoom=9.7)
    fig.update_traces(marker_line_width=0.15)
    fig.update_layout(coloraxis_showscale=False, margin={"r": 0, "t": 0, "l": 0, "b": 0})
    fig.write_image(out / "geometry.png", width=SIZE, height=SIZE)
    print("wrote geometry.png")


def reservoirs(out: Path) -> None:
    df = pd.read_csv(DATA / "london_reservoir_levels.csv")
    df.columns = df.columns.str.strip()
    df["date"] = pd.to_datetime(df["date"], format="mixed", dayfirst=True)
    for col in ("lower_thames_group", "lower_lee_group"):
        df[col] = pd.to_numeric(df[col], errors="coerce")
    # The post's "heartbeat": the average year (climatology by calendar month).
    df["m"] = df["date"].dt.month
    clim = df.groupby("m")[["lower_thames_group", "lower_lee_group"]].mean().reset_index()
    long = clim.melt(id_vars="m", value_vars=["lower_thames_group", "lower_lee_group"],
                     var_name="group", value_name="pct")
    long["group"] = long["group"].map({"lower_thames_group": "Lower Thames",
                                        "lower_lee_group": "Lower Lee"})
    fig = px.line(long, x="m", y="pct", color="group", markers=True,
                  color_discrete_map={"Lower Thames": "#2e8b8b", "Lower Lee": "#1c5fb0"})
    fig.update_traces(line={"width": 3}, marker={"size": 7})
    fig.update_xaxes(visible=False)
    fig.update_yaxes(visible=False)
    fig.update_layout(showlegend=False, margin={"r": 14, "t": 14, "l": 14, "b": 14})
    fig.write_image(out / "reservoirs.png", width=SIZE, height=int(SIZE * 0.82))
    print("wrote reservoirs.png")


def main() -> None:
    parser = argparse.ArgumentParser(description="Generate post thumbnails (Plotly + kaleido).")
    parser.add_argument("--out", default=str(ROOT.parent / "koulakhilesh.github.io"
                                             / "assets" / "thumbs"))
    args = parser.parse_args()
    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)

    df = _plaques()
    blue_plaques(out, df)
    geometry(out, df)
    reservoirs(out)
    print("thumbnails written to", out)


if __name__ == "__main__":
    main()
