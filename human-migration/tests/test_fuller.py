import numpy as np

import fuller as F

CITIES = {
    "London": (-0.13, 51.51), "Nairobi": (36.82, -1.29), "Sydney": (151.21, -33.87),
    "New York": (-74.0, 40.71), "Santiago": (-70.65, -33.45), "Tokyo": (139.69, 35.69),
    "Reykjavik": (-21.94, 64.15), "McMurdo": (166.67, -77.85),
}


def _triangle_contains(tri, z, eps=1e-9):
    a, b, c = tri
    def side(p, q, r):
        return ((q - p).conjugate() * (r - p)).imag
    s = [side(a, b, z), side(b, c, z), side(c, a, z)]
    return all(v >= -eps for v in s) or all(v <= eps for v in s)


def test_24_faces_after_splits():
    assert len(F.FACES) == 24 == len(F.PARENTS)


def test_faces_tile_the_sphere():
    # A dense sample of the sphere: every point lies on at least one face.
    rng = np.random.default_rng(0)
    p = rng.normal(size=(4000, 3))
    p /= np.linalg.norm(p, axis=1, keepdims=True)
    on = np.zeros(len(p), bool)
    for f in F.FACES:
        on |= f.contains(p)
    assert on.all()


def test_shared_edges_agree_after_unfolding():
    # Points along every child/parent edge land in the same place from both faces.
    worst = 0.0
    for i, par in enumerate(F.PARENTS):
        if par < 0:
            continue
        child, parent = F.FACES[i], F.FACES[par]
        a, b = [v for v in child.v if any(np.allclose(v, q) for q in parent.v)]
        for t in np.linspace(0, 1, 7):
            m = (a * (1 - t) + b * t) / np.linalg.norm(a * (1 - t) + b * t)
            worst = max(worst, abs(child.place(m)[0] - parent.place(m)[0]))
    assert worst < 1e-9


def test_whole_faces_are_equilateral_on_the_net():
    for f in F.FACES[:14] + F.FACES[16:19]:  # the 17 faces that were never split
        z = f.place(f.v)
        sides = np.abs(np.diff(np.r_[z, z[:1]]))
        assert np.allclose(sides, sides[0], rtol=1e-9)


def test_cities_land_inside_their_face_triangle():
    for name, (lon, lat) in CITIES.items():
        p = F.orient(lon, lat)
        i = F.face_of(p)
        z = F.project(lon, lat)[0]
        assert _triangle_contains(F.FACES[i].place(F.FACES[i].v), z), name


def test_no_mirroring_and_modest_distortion():
    # A small east step and north step keep their handedness, and their ratio and angle stay near 1 and 90°.
    rng = np.random.default_rng(2)
    for lon, lat in zip(rng.uniform(-180, 180, 600), rng.uniform(-75, 75, 600)):
        d = 0.05
        pts = [(lon, lat), (lon + d / np.cos(np.radians(lat)), lat), (lon, lat + d)]
        if len({F.face_of(F.orient(*p)) for p in pts}) > 1:
            continue
        z = F.project(*zip(*pts))
        east, north = z[1] - z[0], z[2] - z[0]
        angle = np.degrees(np.angle(north / east))
        assert 76 < angle < 104, (lon, lat, angle)
        assert 0.78 < abs(north) / abs(east) < 1.26, (lon, lat)


def test_rotation_matches_d3_convention():
    # d3.geoRotation([90, 0]) sends [0, 0] to [90, 0]; geoRotation([0, 90]) sends it to the north pole.
    assert np.allclose(F.to_lonlat(F.rotation(90, 0, 0) @ F.to_xyz(0, 0)), [90, 0])
    assert np.allclose(F.to_lonlat(F.rotation(0, 90, 0) @ F.to_xyz(0, 0))[1], 90)


def test_clip_ring_keeps_an_inner_ring_and_trims_a_crossing_one():
    f = F.FACES[0]
    c = f.v.sum(0) / np.linalg.norm(f.v.sum(0))
    small = c + 0.01 * np.eye(3)
    small /= np.linalg.norm(small, axis=1, keepdims=True)
    assert len(F.clip_ring(small, f.planes)) == 3
    big = 2 * f.v - c
    big = F.densify(big / np.linalg.norm(big, axis=1, keepdims=True), closed=True)
    out = F.clip_ring(big, f.planes)
    assert len(out) >= 3 and f.contains(out, eps=1e-9).all()
