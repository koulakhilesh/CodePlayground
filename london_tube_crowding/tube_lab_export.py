"""Export compact JSON for the Lab's "Your station's day" companion.

Usage: python london_tube_crowding/tube_lab_export.py --out ../koulakhilesh.github.io/assets/lab/tube-day.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

ROOT = Path(__file__).resolve().parents[1]
DATA = ROOT / "data" / "tube_crowding"
CENTRE_LAT, CENTRE_LON = 51.5074, -0.1278  # same centre and km formula as export_charts.py
DAY_START = "0500"


def day_order(codes) -> list[str]:
    """Slice start codes ordered from 05:00 through the small hours."""
    s = sorted(set(codes))
    return [c for c in s if c >= DAY_START] + [c for c in s if c < DAY_START]


def build_tube_day(crowding: pd.DataFrame, master: pd.DataFrame) -> dict:
    df = crowding.assign(start=crowding["time_slice"].astype(str).str[:4])
    order = day_order(df["start"])
    flows = (df.groupby(["common_name", "start"])["value"].sum()
             .unstack(fill_value=0).reindex(columns=order, fill_value=0))
    lines = df.groupby("common_name")["line"].agg(lambda s: sorted(set(s)))
    m = master.assign(km=np.hypot(
        (master["lat"] - CENTRE_LAT) * 111,
        (master["lon"] - CENTRE_LON) * 111 * np.cos(np.radians(CENTRE_LAT)),
    ))
    km = (df[["common_name", "station_naptan"]].drop_duplicates()
          .merge(m[["naptan", "km"]], left_on="station_naptan", right_on="naptan")
          .groupby("common_name")["km"].mean())
    missing = sorted(set(flows.index) - set(km.dropna().index))
    if missing:
        raise ValueError(f"no master coordinates for: {missing}")
    stations = [{"n": name, "l": list(lines[name]), "km": round(float(km[name]), 1),
                 "v": [int(v) for v in flows.loc[name]]}
                for name in sorted(flows.index)]
    return {"slices": [f"{c[:2]}:{c[2:]}" for c in order], "stations": stations}


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()
    data = build_tube_day(pd.read_csv(DATA / "station_line_crowding.csv"),
                          pd.read_csv(DATA / "stations_master.csv"))
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(json.dumps(data, separators=(",", ":"), allow_nan=False), encoding="utf-8")
    print(f"{len(data['stations'])} stations x {len(data['slices'])} slices -> {args.out}")


if __name__ == "__main__":
    main()
