"""London parkrun: where the 5k events are and who can get to one."""
from __future__ import annotations

import json
import re
import string
import zipfile
from pathlib import Path

import geopandas as gpd
import numpy as np
import pandas as pd
from scipy.stats import spearmanr

BNG = "EPSG:27700"
WGS84 = "EPSG:4326"
UK, FIVE_K = 97, 1

ROOT = Path(__file__).resolve().parents[1]
RAW = ROOT / "data" / "parkrun" / "raw"
UNZ = RAW / "unz"
EVENTS_JSON = RAW / "events.json"
BOROUGHS_SHP = UNZ / "statistical-gis-boundaries-london/ESRI/London_Borough_Excluding_MHW.shp"
LSOA11_SHP = UNZ / "statistical-gis-boundaries-london/ESRI/LSOA_2011_London_gen_MHW.shp"
LSOA21_DIR = UNZ / "LB_shp"
TS007A_ZIP = RAW / "census2021-ts007a.zip"
TS045_ZIP = RAW / "census2021-ts045.zip"
PTAL_CSV = RAW / "ptal_lsoa2011.csv"
NAPTAN_CSV = RAW / "naptan.csv"
GREENSPACE_GPKG = UNZ / "Data/opgrsp_gb.gpkg"


def load_events(path: Path = EVENTS_JSON) -> gpd.GeoDataFrame:
    feats = json.loads(Path(path).read_text(encoding="utf-8"))["events"]["features"]
    df = pd.DataFrame([
        {"id": f["id"], **f["properties"],
         "lon": f["geometry"]["coordinates"][0], "lat": f["geometry"]["coordinates"][1]}
        for f in feats
    ]).rename(columns={"EventLongName": "long_name", "EventShortName": "short_name", "EventLocation": "location"})
    cols = ["id", "eventname", "long_name", "short_name", "location", "countrycode", "seriesid"]
    return gpd.GeoDataFrame(df[cols], geometry=gpd.points_from_xy(df["lon"], df["lat"]), crs=WGS84)


def filter_london_5k(events: gpd.GeoDataFrame, boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    ev = events[(events["countrycode"] == UK) & (events["seriesid"] == FIVE_K)].to_crs(BNG)
    area = boundary.to_crs(BNG).union_all()
    return ev[ev.within(area)].reset_index(drop=True)


def load_boroughs(path: Path = BOROUGHS_SHP) -> gpd.GeoDataFrame:
    # The .prj is British National Grid without an EPSG authority code.
    b = gpd.read_file(path).set_crs(BNG, allow_override=True)
    return b.rename(columns={"NAME": "borough", "GSS_CODE": "code"})[["borough", "code", "geometry"]]


AGE_TOTAL = "Age: Total"
CARS_TOTAL = "Number of cars or vans: Total: All households"
CARS_NONE = "Number of cars or vans: No cars or vans in household"


def centroids(gdf: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    return gpd.GeoDataFrame(index=gdf.index, geometry=gdf.geometry.centroid, crs=gdf.crs)


def join_census(lsoa: gpd.GeoDataFrame, age: pd.DataFrame, cars: pd.DataFrame) -> gpd.GeoDataFrame:
    pop = age.set_index("geography code")[AGE_TOTAL].rename("population")
    car = cars.set_index("geography code")[[CARS_TOTAL, CARS_NONE]].rename(
        columns={CARS_TOTAL: "households", CARS_NONE: "no_car_households"})
    out = lsoa.join(pop, on="lsoa21cd").join(car, on="lsoa21cd")
    out["no_car_share"] = out["no_car_households"] / out["households"]
    return out


def _census_lsoa(zip_path: Path, table: str) -> pd.DataFrame:
    with zipfile.ZipFile(zip_path) as z:
        return pd.read_csv(z.open(f"census2021-{table}-lsoa.csv"))


def load_lsoa() -> gpd.GeoDataFrame:
    parts = [gpd.read_file(p) for p in sorted(LSOA21_DIR.glob("*.shp"))]
    lsoa = pd.concat(parts, ignore_index=True).to_crs(BNG)
    lsoa = gpd.GeoDataFrame(lsoa, geometry="geometry", crs=BNG).rename(columns={"lad22nm": "borough"})
    lsoa = lsoa[["lsoa21cd", "lsoa21nm", "borough", "geometry"]]
    return join_census(lsoa, _census_lsoa(TS007A_ZIP, "ts007a"), _census_lsoa(TS045_ZIP, "ts045"))


def load_lsoa11_ptal() -> gpd.GeoDataFrame:
    shp = gpd.read_file(LSOA11_SHP).set_crs(BNG, allow_override=True)
    ptal = pd.read_csv(PTAL_CSV, dtype={"PTAL": str}).rename(
        columns={"LSOA2011": "lsoa11cd", "AvPTAI2015": "ptal_ai", "PTAL": "ptal"})
    out = shp.rename(columns={"LSOA11CD": "lsoa11cd"})[["lsoa11cd", "geometry"]]
    return out.merge(ptal[["lsoa11cd", "ptal_ai", "ptal"]], on="lsoa11cd", how="left")


def attach_ptal(lsoa: gpd.GeoDataFrame, lsoa11: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    # Nearest = containing polygon (distance 0); also catches centroids on generalised edges.
    hit = gpd.sjoin_nearest(centroids(lsoa), lsoa11[["ptal_ai", "ptal", "geometry"]], how="left")
    hit = hit[~hit.index.duplicated()]
    out = lsoa.copy()
    out["ptal_ai"] = hit["ptal_ai"]
    out["ptal"] = hit["ptal"]
    return out


STATION_MODES = (("ZZLU", "tube"), ("ZZDL", "dlr"), ("ZZCR", "tram"))


def classify_station(atco: str, stop_type: str) -> str:
    if stop_type == "RLY":
        return "rail"
    for code, mode in STATION_MODES:
        if code in atco:
            return mode
    return "other"


def load_stations(path: Path = NAPTAN_CSV) -> gpd.GeoDataFrame:
    # RLY = national rail incl. Overground and Elizabeth line; MET = Tube, DLR, tram.
    cols = ["ATCOCode", "CommonName", "StopType", "Easting", "Northing", "Status"]
    n = pd.read_csv(path, low_memory=False, usecols=cols)
    n = n[n["StopType"].isin(["RLY", "MET"]) & (n["Status"] == "active")].dropna(subset=["Easting", "Northing"])
    n["mode"] = [classify_station(a, t) for a, t in zip(n["ATCOCode"], n["StopType"])]
    out = n.rename(columns={"ATCOCode": "atco", "CommonName": "name"})[["atco", "name", "mode"]]
    return gpd.GeoDataFrame(out, geometry=gpd.points_from_xy(n["Easting"], n["Northing"]), crs=BNG)


def nearest(points: gpd.GeoDataFrame, targets: gpd.GeoDataFrame, label: str) -> pd.DataFrame:
    j = gpd.sjoin_nearest(points[["geometry"]], targets[[label, "geometry"]], how="left", distance_col="distance_m")
    j = j[~j.index.duplicated()]
    return pd.DataFrame(j[[label, "distance_m"]])


def lsoa_access(lsoa: gpd.GeoDataFrame, events: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    near = nearest(centroids(lsoa), events, "short_name")
    out = lsoa.copy()
    out["nearest_event"] = near["short_name"]
    out["dist_m"] = near["distance_m"]
    return out


def station_access(events: gpd.GeoDataFrame, stations: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    any_st = nearest(events, stations, "name")
    tube = nearest(events, stations[stations["mode"] == "tube"], "name")
    out = events[["short_name", "geometry"]].copy()
    out["station"], out["station_m"] = any_st["name"], any_st["distance_m"]
    out["tube_station"], out["tube_m"] = tube["name"], tube["distance_m"]
    return out


LOW_PTAL = {"0", "1a", "1b", "2"}


def weighted_median(values, weights) -> float:
    v = np.asarray(values, dtype=float)
    w = np.asarray(weights, dtype=float)
    order = np.argsort(v, kind="stable")
    cum = np.cumsum(w[order])
    return float(v[order][np.searchsorted(cum, cum[-1] / 2)])


def coverage_by_threshold(lsoa: pd.DataFrame, thresholds_m=(1000, 2000, 5000)) -> pd.DataFrame:
    total = lsoa["population"].sum()
    rows = [{"threshold_m": t, "population": int(lsoa.loc[lsoa["dist_m"] <= t, "population"].sum())}
            for t in thresholds_m]
    out = pd.DataFrame(rows)
    out["share"] = out["population"] / total
    return out


def borough_access(lsoa: pd.DataFrame, threshold_m: int = 2000) -> pd.DataFrame:
    rows = []
    for borough, g in lsoa.groupby("borough"):
        pop = g["population"].sum()
        rows.append({"borough": borough, "population": int(pop),
                     "median_dist_m": weighted_median(g["dist_m"], g["population"]),
                     "share_within": g.loc[g["dist_m"] <= threshold_m, "population"].sum() / pop})
    return pd.DataFrame(rows).sort_values("median_dist_m", ascending=False, ignore_index=True)


def car_free_gap(lsoa: gpd.GeoDataFrame, far_m: int = 2000) -> gpd.GeoDataFrame:
    london_no_car = lsoa["no_car_households"].sum() / lsoa["households"].sum()
    out = lsoa.copy()
    out["far"] = out["dist_m"] > far_m
    out["carless"] = out["no_car_share"] >= london_no_car
    out["low_ptal"] = out["ptal"].isin(LOW_PTAL)
    out["gap"] = out["far"] & out["carless"]
    return out


def catchments(lsoa: pd.DataFrame, events: gpd.GeoDataFrame) -> pd.DataFrame:
    agg = lsoa.groupby("nearest_event").agg(population=("population", "sum"), lsoas=("lsoa21cd", "size"))
    unknown = set(agg.index) - set(events["short_name"])
    if unknown:
        raise ValueError(f"nearest_event not in events: {sorted(unknown)}")
    agg = agg.reindex(events["short_name"], fill_value=0).rename_axis("short_name")
    return agg.sort_values("population", ascending=False, kind="stable").reset_index()


# Task 9: Shape functions — founding order, names, extremes
def id_order_check(events: pd.DataFrame, known: pd.DataFrame) -> tuple[pd.DataFrame, float]:
    t = known.merge(events[["short_name", "id"]], on="short_name", how="inner")
    t["first_event"] = pd.to_datetime(t["first_event"])
    rho = spearmanr(t["id"], t["first_event"].astype(np.int64)).statistic
    return t[["short_name", "id", "first_event", "source"]].sort_values("id", ignore_index=True), float(rho)


def name_terms(events: pd.DataFrame) -> pd.Series:
    base = events["short_name"].str.split(",").str[0].str.strip()
    term = base.str.split().str[-1].where(base.str.contains(" "), "(place name only)")
    return term.value_counts()


def _xy(events: gpd.GeoDataFrame) -> np.ndarray:
    return np.column_stack([events.geometry.x, events.geometry.y])


def event_extremes(events: gpd.GeoDataFrame) -> dict:
    xy = _xy(events)
    d = np.hypot(xy[:, None, 0] - xy[None, :, 0], xy[:, None, 1] - xy[None, :, 1])
    np.fill_diagonal(d, np.inf)
    nn = d.min(axis=1)
    iso = int(nn.argmax())
    i, j = np.unravel_index(int(d.argmin()), d.shape)
    names = events["short_name"].to_numpy()
    return {"most_isolated": names[iso], "isolated_nn_m": float(nn[iso]),
            "closest_pair": tuple(sorted((names[i], names[j]))), "closest_m": float(d[i, j]),
            "median_nn_m": float(np.median(nn))}


# Task 10: London alphabet route
def first_letter(name: str) -> str:
    return re.sub(r"^the\s+", "", name.strip(), flags=re.I)[0].upper()


def missing_letters(events: pd.DataFrame) -> list[str]:
    have = {first_letter(n) for n in events["short_name"]}
    return [c for c in string.ascii_uppercase if c not in have]


def _len(xy: np.ndarray, route: list[int]) -> float:
    return float(np.hypot(*np.diff(xy[route], axis=0).T).sum()) if len(route) > 1 else 0.0


def path_length(events: gpd.GeoDataFrame, route: list[str]) -> float:
    pos = {n: i for i, n in enumerate(events["short_name"])}
    return _len(_xy(events), [pos[n] for n in route])


def _improve(xy: np.ndarray, letter: np.ndarray, route: list[int]) -> list[int]:
    improved = True
    while improved:
        improved = False
        for i in range(len(route) - 1):
            for j in range(i + 1, len(route)):
                new = route[:i] + route[i:j + 1][::-1] + route[j + 1:]
                if _len(xy, new) < _len(xy, route) - 1e-9:
                    route, improved = new, True
        for pos in range(len(route)):
            for alt in np.flatnonzero(letter == letter[route[pos]]):
                new = route[:pos] + [int(alt)] + route[pos + 1:]
                if _len(xy, new) < _len(xy, route) - 1e-9:
                    route, improved = new, True
    return route


def alphabet_route(events: gpd.GeoDataFrame) -> list[str]:
    xy = _xy(events)
    letter = np.array([first_letter(n) for n in events["short_name"]])
    best: list[int] | None = None
    for start in range(len(events)):
        route, seen = [start], {letter[start]}
        while True:
            cand = np.flatnonzero(~np.isin(letter, list(seen)))
            if cand.size == 0:
                break
            nxt = int(cand[np.argmin(np.hypot(*(xy[cand] - xy[route[-1]]).T))])
            route.append(nxt)
            seen.add(letter[nxt])
        route = _improve(xy, letter, route)
        if best is None or _len(xy, route) < _len(xy, best):
            best = route
    return events["short_name"].to_numpy()[best].tolist()


# Task 11: Where should the next parkrun go?
CANDIDATE_FUNCTIONS = ("Public Park Or Garden", "Playing Field")


def load_greenspace(boundary: gpd.GeoDataFrame) -> gpd.GeoDataFrame:
    g = gpd.read_file(GREENSPACE_GPKG, layer="greenspace_site",
                      bbox=tuple(boundary.to_crs(BNG).total_bounds))
    g = g.rename(columns={"distinctive_name_1": "name"})
    g["name"] = g["name"].fillna("Unnamed " + g["function"].str.lower())
    return g[["id", "function", "name", "geometry"]].to_crs(BNG)


def candidate_sites(greenspace: gpd.GeoDataFrame, boundary: gpd.GeoDataFrame, events: gpd.GeoDataFrame,
                    min_ha: float = 10, exclude_m: float = 1000) -> gpd.GeoDataFrame:
    area = boundary.to_crs(BNG).union_all()
    g = greenspace[greenspace["function"].isin(CANDIDATE_FUNCTIONS)].copy()
    g = g[g.representative_point().within(area)]
    g["area_ha"] = g.area / 10_000
    g = g[g["area_ha"] >= min_ha]
    return g[g.distance(events.union_all()) > exclude_m].reset_index(drop=True)


def best_new_sites(candidates: gpd.GeoDataFrame, lsoa: gpd.GeoDataFrame,
                   radius_m: float = 2000, k: int = 5) -> gpd.GeoDataFrame:
    cent = centroids(lsoa)
    cx, cy = cent.geometry.x.to_numpy(), cent.geometry.y.to_numpy()
    pop = lsoa["population"].to_numpy()
    dist = lsoa["dist_m"].to_numpy(dtype=float).copy()
    pts = candidates.representative_point()
    picks = []
    for _ in range(k):
        best = None
        for idx, p in pts.items():
            d = np.hypot(cx - p.x, cy - p.y)
            gain = int(pop[(dist > radius_m) & (d <= radius_m)].sum())
            if best is None or gain > best[1]:
                best = (idx, gain, d)
        if best is None or best[1] == 0:
            break
        idx, gain, d = best
        dist = np.minimum(dist, d)
        row = candidates.loc[idx]
        picks.append({"site": row["name"], "function": row["function"], "area_ha": float(row["area_ha"]),
                      "added_population": gain, "geometry": pts[idx]})
    return gpd.GeoDataFrame(picks, geometry="geometry", crs=BNG)
