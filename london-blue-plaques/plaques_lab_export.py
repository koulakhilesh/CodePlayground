"""Export compact JSON for the Lab's Voronoi playground.

Same filter and projection as blue_plaques_geospatial.ipynb (dropna on lat/lng, EPSG:27700).
Usage: python london-blue-plaques/plaques_lab_export.py --out ../koulakhilesh.github.io/assets/lab/plaques.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "blue_plaques_2026-08.csv"


def tidy_name(name) -> str:
    if pd.isna(name):
        return ""
    s = " ".join(str(name).split())
    return s.title() if s.isupper() else s


def build_plaques(df: pd.DataFrame) -> dict:
    geo = df.dropna(subset=["lat", "lng"])
    pts = gpd.GeoSeries(gpd.points_from_xy(geo["lng"], geo["lat"]), crs=4326).to_crs(27700)
    return {
        "crs": "EPSG:27700",
        "x": [int(round(v)) for v in pts.x],
        "y": [int(round(v)) for v in pts.y],
        "n": [tidy_name(v) for v in geo["name"]],
    }


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--source", type=Path, default=SOURCE)
    args = ap.parse_args()
    data = build_plaques(pd.read_csv(args.source))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False, allow_nan=False),
                        encoding="utf-8")
    print(f"{len(data['x'])} plaques -> {args.out}")


if __name__ == "__main__":
    main()
