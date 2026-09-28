import json
import re

import numpy as np
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


def test_a_continent_sized_polygon_is_not_torn():
    # A polygon spanning several faces keeps all of its interior (does not yet reproduce the torn-Africa bug).
    big = box(-20, -35, 60, 40)
    land = shapely.union_all(M.project_land([big]))
    lon, lat = np.meshgrid(np.linspace(-18, 58, 20), np.linspace(-33, 38, 20))
    inside = [land.buffer(1e-3).contains(Point(z.real, z.imag)) for z in F.project(lon.ravel(), lat.ravel())]
    assert all(inside)


def test_africa_top_left_and_the_americas_to_the_right():
    world, migration = M.build([box(20, -5, 30, 5)], min_area_px=0)
    lab = {d["t"]: d["xy"] for d in world["labels"]}
    assert lab["Africa"][0] < lab["Asia"][0] < lab["North America"][0] < lab["Antarctica"][0]
    assert lab["Africa"][1] < lab["Australia"][1]
    assert lab["Australia"][0] < lab["Asia"][0]
