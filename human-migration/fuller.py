"""Buckminster Fuller's icosahedral world map (the "Fuller projection").

Face layout, split faces and unfolding tree follow d3-geo-polygon's airocean.js
(ISC licence; Jason Davies, Enrico Spinielli, Philippe Rivière). The per-face transform is
Robert W. Gray's exact equations ("Exact Transformation Equations for Fuller's World Map",
Cartographica 32(3), 1995), as in d3-geo-polygon's public-domain grayfuller.js.

Geometry is clipped to each face on the sphere (great-circle half-spaces), so nothing is
ever projected from outside its own triangle.
"""
from __future__ import annotations

import numpy as np

THETA = np.degrees(np.arctan(0.5))
SQRT3 = np.sqrt(3)
Z = np.sqrt(5 + 2 * np.sqrt(5)) / np.sqrt(15)
EL = np.sqrt(8) / np.sqrt(5 + np.sqrt(5))
DVE = np.sqrt(3 + np.sqrt(5)) / np.sqrt(5 + np.sqrt(5))
# Fuller's orientation of the icosahedron: all 12 vertices fall in the ocean.
ROTATE = (-83.65929, 25.44458, -87.45184)

_FACES = [
    [0, 3, 11], [0, 5, 3], [0, 7, 5], [0, 9, 7], [0, 11, 9],
    [2, 11, 3], [3, 4, 2], [4, 3, 5], [5, 6, 4], [6, 5, 7], [7, 8, 6], [8, 7, 9], [9, 10, 8],
    [10, 9, 11], [11, 2, 10],
    [1, 2, 4], [1, 4, 6], [1, 6, 8], [1, 8, 10], [1, 10, 2],
]
# Parent of each of the 24 (split) faces in the unfolded net; face 0 is the root.
PARENTS = [-1, 0, 1, 11, 13, 6, 7, 1, 7, 8, 9, 10, 11, 12, 13, 6, 8, 10, 17, 21, 16, 15, 19, 19]


def to_xyz(lon, lat) -> np.ndarray:
    lon, lat = np.radians(np.asarray(lon, float)), np.radians(np.asarray(lat, float))
    return np.stack([np.cos(lat) * np.cos(lon), np.cos(lat) * np.sin(lon), np.sin(lat)], axis=-1)


def to_lonlat(v) -> np.ndarray:
    v = np.asarray(v, float)
    return np.degrees(np.stack([np.arctan2(v[..., 1], v[..., 0]), np.arcsin(np.clip(v[..., 2], -1, 1))], -1))


def rotation(dl: float, dp: float, dg: float) -> np.ndarray:
    """d3-geo's rotate([dl, dp, dg]) as a matrix acting on unit vectors."""
    l, p, g = np.radians([dl, dp, dg])
    rz = np.array([[np.cos(l), -np.sin(l), 0], [np.sin(l), np.cos(l), 0], [0, 0, 1]])
    ry = np.array([[np.cos(p), 0, -np.sin(p)], [0, 1, 0], [np.sin(p), 0, np.cos(p)]])
    rx = np.array([[1, 0, 0], [0, np.cos(g), -np.sin(g)], [0, np.sin(g), np.cos(g)]])
    return rx @ ry @ rz


def _unit(v):
    v = np.asarray(v, float)
    return v / np.linalg.norm(v, axis=-1, keepdims=True)


def gray_fuller(gx, gy):
    """Gray's transform from a face's (scaled) gnomonic plane to Fuller's triangle."""
    a1 = np.arctan2(2 * gy / SQRT3 + EL / 3 - EL / 2, DVE)
    a2 = np.arctan2(gx - gy / SQRT3 + EL / 3 - EL / 2, DVE)
    a3 = np.arctan2(EL / 3 - gx - gy / SQRT3 - EL / 2, DVE)
    return SQRT3 * (a2 - a3), 2 * a1 - a2 - a3


class Face:
    def __init__(self, verts, centre):
        self.v = np.array(verts)
        clat = to_lonlat(centre)
        direction = 0 if abs(clat[1] - 52.62) < 1 or abs(clat[1] + 10.81) < 1 else 60
        self.m = rotation(-clat[0], -clat[1], direction)
        self.planes = []
        for i in range(3):
            a, b, c = self.v[i], self.v[(i + 1) % 3], self.v[(i + 2) % 3]
            n = np.cross(a, b)
            self.planes.append(n if n @ c > 0 else -n)
        self.planes = np.array(self.planes)
        self.s, self.t = 1 + 0j, 0j

    def local(self, p) -> np.ndarray:
        """Unit vectors (already in Fuller's orientation) -> complex coords in the face's triangle."""
        q = np.atleast_2d(p) @ self.m.T
        x, y = gray_fuller(Z * q[:, 1] / q[:, 0], Z * q[:, 2] / q[:, 0])
        return x + 1j * y

    def place(self, p) -> np.ndarray:
        return self.s * self.local(p) + self.t

    def contains(self, p, eps=1e-12) -> np.ndarray:
        return (np.atleast_2d(p) @ self.planes.T >= -eps).all(axis=1)


def build_faces() -> list[Face]:
    verts = to_xyz([0, 0] + [(i * 36 + 180) % 360 - 180 for i in range(10)],
                   [90, -90] + [THETA if i & 1 else -THETA for i in range(10)])
    tri = [[verts[i] for i in f] for f in _FACES]
    cen = [_unit(sum(f)) for f in tri]
    faces = [Face(tri[i], cen[i]) for i in range(20)]

    # Split face 15 at its centroid into faces 15, 20 and 21.
    v1, v2, v4 = tri[15]
    c15 = cen[15]
    faces[15] = Face([c15, v2, v4], c15)
    faces.append(Face([v1, c15, v4], c15))
    faces.append(Face([v1, v2, c15], c15))
    # Split face 14 at the middle of its v2-v10 edge (faces 14, 22), and face 19 to match (19, 23).
    v11, _, v10 = tri[14]
    c14 = cen[14]
    g = [p / (p @ c14) for p in (v2, v10)]
    mid = _unit((g[0] + g[1]) / 2)
    faces[14] = Face([v11, mid, v10], c14)
    faces.append(Face([v11, v2, mid], c14))
    c19 = cen[19]
    faces[19] = Face([v1, mid, v2], c19)
    faces.append(Face([mid, v1, v10], c19))

    done = {0}
    while len(done) < len(faces):
        for i, par in enumerate(PARENTS):
            if i in done or par not in done:
                continue
            child, parent = faces[i], faces[par]
            shared = [p for p in child.v if any(np.allclose(p, q, atol=1e-9) for q in parent.v)]
            assert len(shared) == 2, (i, par)
            a, b = child.local(np.array(shared))
            pa, pb = parent.place(np.array(shared))
            child.s = (pb - pa) / (b - a)
            child.t = pa - child.s * a
            done.add(i)
    return faces


FACES = build_faces()
_R = rotation(*ROTATE)


def orient(lon, lat) -> np.ndarray:
    return to_xyz(lon, lat) @ _R.T


def densify(p: np.ndarray, max_deg: float = 0.5, closed: bool = False) -> np.ndarray:
    """Insert great-circle points so no step is longer than max_deg."""
    pts = np.vstack([p, p[:1]]) if closed else p
    out = [pts[0]]
    for a, b in zip(pts[:-1], pts[1:]):
        ang = np.degrees(np.arccos(np.clip(a @ b, -1, 1)))
        n = int(np.ceil(ang / max_deg))
        for k in range(1, n + 1):
            out.append(_unit(a + (b - a) * k / n))
    out = np.array(out)
    return out[:-1] if closed else out


def clip_ring(ring: np.ndarray, planes: np.ndarray) -> np.ndarray:
    """Sutherland-Hodgman on the sphere; exact because each plane passes through the origin."""
    pts = list(ring)
    for n in planes:
        if not pts:
            break
        out, d = [], [n @ p for p in pts]
        for i in range(len(pts)):
            j = (i + 1) % len(pts)
            if d[i] >= 0:
                out.append(pts[i])
            if (d[i] >= 0) != (d[j] >= 0):
                out.append(_unit(pts[i] + (pts[j] - pts[i]) * (d[i] / (d[i] - d[j]))))
        pts = out
    return np.array(pts)


def clip_line(line: np.ndarray, planes: np.ndarray) -> list[np.ndarray]:
    runs = [list(line)]
    for n in planes:
        nxt = []
        for run in runs:
            cur, d = [], [n @ p for p in run]
            for i in range(len(run)):
                if d[i] >= 0:
                    cur.append(run[i])
                if i + 1 < len(run) and (d[i] >= 0) != (d[i + 1] >= 0):
                    cur.append(_unit(run[i] + (run[i + 1] - run[i]) * (d[i] / (d[i] - d[i + 1]))))
                    if d[i] >= 0:
                        nxt.append(cur)
                        cur = []
            if len(cur) > 1:
                nxt.append(cur)
        runs = [r for r in nxt if len(r) > 1]
    return [np.array(r) for r in runs]


def face_of(p: np.ndarray) -> int:
    for i, f in enumerate(FACES):
        if f.contains(p)[0]:
            return i
    raise ValueError("point on no face")


def project(lon, lat) -> np.ndarray:
    """Project lon/lat points to complex net coordinates (before the final layout rotation)."""
    p = np.atleast_2d(orient(lon, lat))
    return np.array([FACES[face_of(q)].place(q)[0] for q in p])
