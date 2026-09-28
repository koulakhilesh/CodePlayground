"""Export the Fuller-projection world map and migration routes for the site's game page.

Usage:
  python human-migration/migration_export.py --out ../koulakhilesh.github.io/assets/lab
Land outlines: Natural Earth 1:50m land (public domain), downloaded to data/natural_earth/.
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path

import geopandas as gpd
import numpy as np
import shapely
from shapely.geometry import LineString, MultiPolygon, Polygon, box

import fuller as F
from stops import LABELS, ORIGIN, STOPS

ROOT = Path(__file__).resolve().parents[1]
SOURCE = ROOT / "data" / "natural_earth" / "ne_50m_land.geojson"
# Final layout: turn the net 60° clockwise so Africa sits top-left, Australia bottom-left and the
# Americas run off to the right, with the triangle edges level.
LAYOUT_DEG = -60.0
WIDTH = 10000  # output units across the map; coordinates are integers
PX = WIDTH / 1200  # one pixel when the map is drawn 1200 px wide


def _rings(geom):
    polys = geom.geoms if isinstance(geom, MultiPolygon) else [geom]
    for poly in polys:
        yield poly.exterior, list(poly.interiors)


def _to_sphere(ring) -> np.ndarray:
    ll = np.asarray(shapely.segmentize(ring, 1.0).coords)[:-1]
    return F.densify(F.orient(ll[:, 0], ll[:, 1]), closed=True)


def _face_poly(face: F.Face, ring: np.ndarray):
    clipped = F.clip_ring(ring, face.planes)
    if len(clipped) < 3:
        return None
    z = face.place(clipped)
    fixed = shapely.make_valid(Polygon(np.c_[z.real, z.imag]))
    poly = shapely.unary_union([g for g in getattr(fixed, "geoms", [fixed]) if g.area > 0])
    return None if poly.is_empty else poly


def _tiles(geoms, size: int = 10):
    """Cut land into lon/lat tiles: clipping a whole continent on the sphere can wrap the wrong way."""
    for geom in geoms:
        x0, y0, x1, y1 = geom.bounds
        for x in range(int(np.floor(x0 / size)) * size, int(np.ceil(x1)), size):
            for y in range(int(np.floor(y0 / size)) * size, int(np.ceil(y1)), size):
                piece = geom.intersection(box(x, y, x + size, y + size))
                for poly in getattr(piece, "geoms", [piece]):
                    if isinstance(poly, Polygon) and not poly.is_empty:
                        yield poly


def project_land(geoms) -> list:
    """Clip every land tile to each face on the sphere, place it on the net, then merge."""
    pieces = []
    for geom in _tiles(geoms):
        for ext, holes in _rings(geom):
            e = _to_sphere(ext)
            hs = [_to_sphere(h) for h in holes]
            for face in F.FACES:
                if ((e @ face.planes.T) < 0).all(axis=0).any():
                    continue
                poly = _face_poly(face, e)
                if poly is None:
                    continue
                for h in hs:
                    hp = _face_poly(face, h)
                    if hp is not None:
                        poly = poly.difference(hp)
                pieces.append(poly)
    eps = 2e-3  # net units, about 0.15 px; closes hairline seams between tiles
    merged = shapely.unary_union(shapely.set_precision(pieces, 1e-7)).buffer(eps).buffer(-eps)
    return list(merged.geoms) if hasattr(merged, "geoms") else [merged]


def project_lines(lines) -> list[np.ndarray]:
    out = []
    for line in lines:
        for face in F.FACES:
            for run in F.clip_line(line, face.planes):
                out.append(face.place(run))
    return out


def graticule(step: int = 15) -> list[np.ndarray]:
    lines = []
    for lat in range(-90 + step, 90, step):
        lon = np.arange(-180, 180.5, 1.0)
        lines.append(F.orient(lon, np.full_like(lon, lat)))
    for lon in range(-180, 180, step):
        lat = np.arange(-90 + step, 90 - step + 0.5, 1.0)
        lines.append(F.orient(np.full_like(lat, lon), lat))
    return project_lines(lines)


def route_pieces(waypoints) -> list[np.ndarray]:
    """Great-circle legs through lon/lat waypoints, split where the net is cut, then smoothed."""
    ll = np.asarray(waypoints, float)
    p = F.densify(F.orient(ll[:, 0], ll[:, 1]), max_deg=0.5)
    z = np.array([F.FACES[F.face_of(q)].place(q)[0] for q in p])
    step = np.abs(np.diff(z))
    cuts = np.where(step > 10 * np.median(step))[0]
    return [_chaikin(seg) for seg in np.split(z, cuts + 1) if len(seg) > 1]


def _chaikin(z: np.ndarray, n: int = 3) -> np.ndarray:
    for _ in range(n):
        if len(z) < 3:
            break
        q = 0.75 * z[:-1] + 0.25 * z[1:]
        r = 0.25 * z[:-1] + 0.75 * z[1:]
        z = np.r_[z[:1], np.c_[q, r].ravel(), z[-1:]]
    return z


class Layout:
    """Rotate the net, flip to screen y-down and scale to integer units."""

    def __init__(self, parts, margin: float = 0.025):
        self.rot = np.exp(1j * np.radians(LAYOUT_DEG))
        pts = self._turn(np.concatenate(parts))
        span = pts.real.max() - pts.real.min()
        self.lo = pts.real.min() + 1j * pts.imag.min() - margin * span * (1 + 1j)
        self.k = WIDTH / (span * (1 + 2 * margin))
        self.w = WIDTH
        self.h = int(np.ceil((pts.imag.max() - pts.imag.min() + 2 * margin * span) * self.k))

    def _turn(self, z):
        z = np.asarray(z) * self.rot
        return z.real - 1j * z.imag

    def flat(self, z, tol: float = 0.0) -> list[int]:
        s = (self._turn(z) - self.lo) * self.k
        xy = np.c_[s.real, s.imag]
        if tol and len(xy) > 2:
            xy = np.asarray(LineString(xy).simplify(tol).coords)
        return [int(round(v)) for v in xy.ravel()]


def build(geoms, min_area_px: float = 4.0, tol_px: float = 0.6) -> tuple[dict, dict]:
    land = project_land(geoms)
    paths = {s["id"]: route_pieces(s["route"]) for s in STOPS}
    layout = Layout([np.asarray(g.exterior.coords) @ [1, 1j] for g in land] +
                    [seg for segs in paths.values() for seg in segs])
    tol, min_area = tol_px * PX, min_area_px * (PX / layout.k) ** 2
    rings = []
    for poly in sorted(land, key=lambda g: -g.area):
        if poly.area < min_area:
            continue
        for ring in [poly.exterior, *poly.interiors]:
            rings.append(layout.flat(np.asarray(ring.coords) @ [1, 1j], tol))
    world = {
        "w": layout.w, "h": layout.h,
        "land": rings,
        "grat": [layout.flat(line, tol) for line in graticule()],
        "faces": [layout.flat(f.place(f.v)) for f in F.FACES],
        "labels": [{"t": t, "xy": layout.flat(F.project(*ll))} for t, ll in LABELS],
    }
    stops = []
    for s in STOPS:
        path = [layout.flat(seg, 0.4 * PX) for seg in paths[s["id"]]]
        stops.append({k: v for k, v in s.items() if k != "route"} |
                     {"path": path, "site": layout.flat(F.project(*s["route"][-1]))})
    migration = {"origin": {**ORIGIN, "xy": layout.flat(F.project(*ORIGIN["ll"]))}, "stops": stops}
    return world, migration


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--out", type=Path, required=True)
    ap.add_argument("--source", type=Path, default=SOURCE)
    args = ap.parse_args()
    world, migration = build(gpd.read_file(args.source).geometry)
    args.out.mkdir(parents=True, exist_ok=True)
    for name, data in (("fuller-world.json", world), ("migration.json", migration)):
        (args.out / name).write_text(json.dumps(data, separators=(",", ":"), ensure_ascii=False,
                                                allow_nan=False), encoding="utf-8")
    n = sum(len(r) // 2 for r in world["land"])
    print(f"{len(world['land'])} land rings, {n} points; {len(migration['stops'])} stops -> {args.out}")


if __name__ == "__main__":
    main()
