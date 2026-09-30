import json
import re

import numpy as np
import pytest
import shapely
from shapely.geometry import Point, Polygon, box

import fuller as F
import migration_export as M
from stops import ORIGIN, STOPS

DOI = re.compile(r"^10\.\d{4,}/\S+$")


def test_stop_ranges_fit_the_slider_and_are_ordered():
    for s in STOPS:
        assert 500 <= s["lo"] < s["hi"] <= 300000, s["id"]
        assert isinstance(s["lo"], int) and isinstance(s["hi"], int)


def test_every_stop_is_cited_with_a_doi():
    for s in STOPS + [ORIGIN]:
        assert s["cite"], s.get("id", "origin")
        for c in s["cite"]:
            assert c["t"] and DOI.match(c["doi"]), c


def test_routes_join_up_into_one_walk():
    ids = [s["id"] for s in STOPS]
    assert len(ids) == len(set(ids)) == 8
    ends = [tuple(ORIGIN["ll"])]
    for s in STOPS:
        assert tuple(s["route"][0]) in ends, f"{s['id']} does not start at an earlier site"
        ends.append(tuple(s["route"][-1]))


def test_a_route_across_a_cut_is_split():
    # Fiji to New Zealand crosses one of the net's cuts in the Pacific.
    assert len(M.route_pieces([(178.0, -17.8), (174.1, -41.5)])) == 2
    assert len(M.route_pieces([(35.0, 32.7), (11.6, 50.7)])) == 1


def test_build_outputs_integer_geometry_inside_the_frame():
    land = [box(20, -5, 30, 5), Polygon([(130, -20), (140, -20), (140, -12), (130, -12)])]
    world, migration = M.build(land, min_area_px=0)
    assert world["w"] == M.WIDTH and 0 < world["h"] < M.WIDTH
    assert len(world["land"]) >= 2 and len(world["faces"]) == 24
    for ring in world["land"] + [p for s in migration["stops"] for p in s["path"]]:
        assert len(ring) % 2 == 0 and all(isinstance(v, int) for v in ring)
        xy = np.array(ring).reshape(-1, 2)
        assert (xy >= 0).all() and (xy[:, 0] <= world["w"]).all() and (xy[:, 1] <= world["h"]).all()
    assert [s["id"] for s in migration["stops"]] == [s["id"] for s in STOPS]
    assert all("route" not in s and s["path"] and len(s["site"]) == 2 for s in migration["stops"])
    json.dumps(world, allow_nan=False)
    json.dumps(migration, allow_nan=False)


def test_a_self_crossing_clipped_ring_keeps_both_lobes():
    # Regression: clipped continent rings can cross themselves; buffer(0) dropped a lobe (Cairo, Lagos).
    f = F.FACES[0]
    c = f.v.mean(0) / np.linalg.norm(f.v.mean(0))
    u = np.cross(c, [0, 0, 1.0]); u /= np.linalg.norm(u)
    w = np.cross(c, u)
    bowtie = np.array([c + 0.1 * (a * u + b * w) for a, b in ((-1, -1), (1, 1), (1, -1), (-1, 1))])
    bowtie /= np.linalg.norm(bowtie, axis=1, keepdims=True)
    poly = M._face_poly(f, bowtie)
    lobes = getattr(poly, "geoms", [poly])
    assert len(lobes) == 2 and all(g.area > 0 for g in lobes)


@pytest.mark.skipif(not M.SOURCE.exists(), reason="Natural Earth land not downloaded")
def test_real_coastlines_keep_known_places_on_land():
    import geopandas as gpd
    land = shapely.union_all(M.project_land(gpd.read_file(M.SOURCE).geometry)).buffer(1e-3)
    places = {"Cairo": (31, 28), "Riyadh": (45, 24), "Lagos": (5, 8), "Dakar": (-15.5, 14.5),
              "Reykjavik": (-19, 64.8), "Tokyo": (138.5, 36), "Wellington": (175.5, -39.5),
              "Hawaii": (-155.5, 19.6), "Tierra del Fuego": (-68.5, -54), "Antarctica": (0, -80)}
    for name, ll in places.items():
        z = F.project(*ll)[0]
        assert land.contains(Point(z.real, z.imag)), name


def test_route_breaks_only_at_real_cuts_in_the_net():
    # The New Zealand voyage is drawn in pieces; each break must sit on the outer edge of Fuller's net.
    net = shapely.union_all([Polygon(np.c_[z.real, z.imag]) for z in (f.place(f.v) for f in F.FACES)])
    edge = net.boundary
    nz = next(s for s in STOPS if s["id"] == "new-zealand")
    pieces = M.route_pieces(nz["route"])
    assert len(pieces) > 1
    tol = 0.02 * abs(F.FACES[0].place(F.FACES[0].v[:1])[0] - F.FACES[0].place(F.FACES[0].v[1:2])[0])
    for a, b in zip(pieces[:-1], pieces[1:]):
        for z in (a[-1], b[0]):
            assert edge.distance(Point(z.real, z.imag)) < tol
    for s in STOPS:
        if s["id"] != "new-zealand":
            assert len(M.route_pieces(s["route"])) == 1, s["id"]


def test_africa_top_left_and_the_americas_to_the_right():
    world, migration = M.build([box(20, -5, 30, 5)], min_area_px=0)
    lab = {d["t"]: d["xy"] for d in world["labels"]}
    assert lab["Africa"][0] < lab["Asia"][0] < lab["North America"][0] < lab["Antarctica"][0]
    assert lab["Africa"][1] < lab["Australia"][1]
    assert lab["Australia"][0] < lab["Asia"][0]
