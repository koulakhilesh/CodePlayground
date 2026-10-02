import json

import geopandas as gpd
import numpy as np
import pandas as pd
import pytest
from shapely.geometry import Point, box

import london_parkrun as lp


def _feature(i, name, lon, lat, country=97, series=1):
    return {"id": i, "type": "Feature", "geometry": {"type": "Point", "coordinates": [lon, lat]},
            "properties": {"eventname": name.lower().replace(" ", ""), "EventLongName": f"{name} parkrun",
                           "EventShortName": name, "LocalisedEventLongName": None,
                           "countrycode": country, "seriesid": series, "EventLocation": name}}


@pytest.fixture
def events_json(tmp_path):
    feats = [
        _feature(1, "Bushy Park", -0.335791, 51.410992),
        _feature(5, "Woodhouse Moor", -1.56009, 53.808582),
        _feature(194, "Bushy juniors", -0.332639, 51.420504, series=2),
        _feature(13, "Amager Faelled", 12.575108, 55.653057, country=23),
    ]
    p = tmp_path / "events.json"
    p.write_text(json.dumps({"countries": {}, "events": {"type": "FeatureCollection", "features": feats}}))
    return p


def test_load_events_flattens_features(events_json):
    ev = lp.load_events(events_json)
    assert list(ev["short_name"]) == ["Bushy Park", "Woodhouse Moor", "Bushy juniors", "Amager Faelled"]
    assert ev.crs.to_epsg() == 4326
    assert ev.loc[0, "geometry"].x == pytest.approx(-0.335791)
    assert {"id", "long_name", "location", "countrycode", "seriesid"} <= set(ev.columns)


def test_filter_london_5k_keeps_uk_5k_inside_boundary(events_json):
    ev = lp.load_events(events_json)
    boundary = gpd.GeoDataFrame(geometry=[box(-0.6, 51.2, 0.4, 51.7)], crs=lp.WGS84)
    out = lp.filter_london_5k(ev, boundary)
    assert list(out["short_name"]) == ["Bushy Park"]
    assert out.crs.to_epsg() == 27700
    assert list(out.index) == [0]


def _square(x, y, s=100):
    return box(x, y, x + s, y + s)


def test_join_census_adds_population_and_car_share():
    lsoa = gpd.GeoDataFrame({"lsoa21cd": ["A", "B"]}, geometry=[_square(0, 0), _square(200, 0)], crs=lp.BNG)
    age = pd.DataFrame({"geography code": ["A", "B"], "Age: Total": [1000, 1500]})
    cars = pd.DataFrame({
        "geography code": ["A", "B"],
        "Number of cars or vans: Total: All households": [400, 600],
        "Number of cars or vans: No cars or vans in household": [100, 450],
    })
    out = lp.join_census(lsoa, age, cars)
    assert list(out["population"]) == [1000, 1500]
    assert list(out["households"]) == [400, 600]
    assert list(out["no_car_households"]) == [100, 450]
    assert list(out["no_car_share"]) == pytest.approx([0.25, 0.75])


def test_attach_ptal_uses_containing_2011_polygon():
    lsoa21 = gpd.GeoDataFrame({"lsoa21cd": ["N1", "N2"]},
                              geometry=[_square(10, 10, 20), _square(150, 10, 20)], crs=lp.BNG)
    lsoa11 = gpd.GeoDataFrame({"lsoa11cd": ["O1", "O2"], "ptal_ai": [5.0, 40.0], "ptal": ["1b", "5"]},
                              geometry=[_square(0, 0), _square(100, 0)], crs=lp.BNG)
    out = lp.attach_ptal(lsoa21, lsoa11)
    assert list(out["ptal"]) == ["1b", "5"]
    assert list(out["ptal_ai"]) == [5.0, 40.0]
    assert len(out) == 2


def _events_bng(names_xy):
    return gpd.GeoDataFrame({"short_name": [n for n, _, _ in names_xy]},
                            geometry=[Point(x, y) for _, x, y in names_xy], crs=lp.BNG)


@pytest.mark.parametrize("atco,stype,mode", [
    ("9100CLPHMJC", "RLY", "rail"), ("9400ZZLUSTD", "MET", "tube"),
    ("9400ZZDLSTD", "MET", "dlr"), ("9400ZZCRWIM", "MET", "tram"), ("9400ZZRLXXX", "MET", "other"),
])
def test_classify_station(atco, stype, mode):
    assert lp.classify_station(atco, stype) == mode


def test_nearest_returns_label_and_metres():
    pts = gpd.GeoDataFrame(geometry=[Point(0, 0), Point(1000, 0)], crs=lp.BNG)
    ev = _events_bng([("West", 0, 300), ("East", 1000, 400)])
    out = lp.nearest(pts, ev, "short_name")
    assert list(out["short_name"]) == ["West", "East"]
    assert list(out["distance_m"]) == pytest.approx([300, 400])


def test_lsoa_access_uses_centroids():
    lsoa = gpd.GeoDataFrame({"lsoa21cd": ["A"], "population": [10]},
                            geometry=[box(-100, -100, 100, 100)], crs=lp.BNG)
    ev = _events_bng([("Here", 0, 500), ("There", 0, 5000)])
    out = lp.lsoa_access(lsoa, ev)
    assert out.loc[0, "nearest_event"] == "Here"
    assert out.loc[0, "dist_m"] == pytest.approx(500)


def test_station_access_any_and_tube():
    ev = _events_bng([("Park", 0, 0)])
    st = gpd.GeoDataFrame({"name": ["Rail stop", "Tube stop"], "mode": ["rail", "tube"]},
                          geometry=[Point(200, 0), Point(900, 0)], crs=lp.BNG)
    out = lp.station_access(ev, st)
    row = out.iloc[0]
    assert (row["station"], row["tube_station"]) == ("Rail stop", "Tube stop")
    assert (row["station_m"], row["tube_m"]) == pytest.approx((200, 900))


@pytest.fixture
def toy_lsoa():
    return gpd.GeoDataFrame({
        "lsoa21cd": ["A", "B", "C", "D"],
        "borough": ["North", "North", "South", "South"],
        "population": [100, 300, 200, 400],
        "dist_m": [500.0, 1500.0, 2500.0, 6000.0],
        "households": [50, 100, 100, 200],
        "no_car_households": [10, 20, 80, 150],
        "no_car_share": [0.2, 0.2, 0.8, 0.75],
        "ptal": ["6a", "3", "1b", "4"],
        "nearest_event": ["Alpha", "Alpha", "Beta", "Beta"],
    }, geometry=[Point(i, 0) for i in range(4)], crs=lp.BNG)


def test_weighted_median():
    assert lp.weighted_median([1, 2, 3], [1, 1, 10]) == 3
    assert lp.weighted_median([4, 1, 3, 2], [1, 1, 1, 1]) == 2


def test_coverage_by_threshold(toy_lsoa):
    cov = lp.coverage_by_threshold(toy_lsoa)
    assert list(cov["threshold_m"]) == [1000, 2000, 5000]
    assert list(cov["population"]) == [100, 400, 600]
    assert list(cov["share"]) == pytest.approx([0.1, 0.4, 0.6])


def test_borough_access(toy_lsoa):
    b = lp.borough_access(toy_lsoa).set_index("borough")
    assert b.loc["North", "population"] == 400
    assert b.loc["North", "median_dist_m"] == 1500
    assert b.loc["South", "median_dist_m"] == 6000
    assert b.loc["North", "share_within"] == pytest.approx(1.0)
    assert b.loc["South", "share_within"] == pytest.approx(0.0)
    assert list(b.index) == ["South", "North"]


def test_car_free_gap(toy_lsoa):
    out = lp.car_free_gap(toy_lsoa)
    assert list(out["far"]) == [False, False, True, True]
    assert list(out["carless"]) == [False, False, True, True]
    assert list(out["low_ptal"]) == [False, False, True, False]
    assert list(out["gap"]) == [False, False, True, True]


def test_catchments_include_empty_events(toy_lsoa):
    ev = _events_bng([("Alpha", 0, 0), ("Beta", 1, 0), ("Gamma", 2, 0)])
    c = lp.catchments(toy_lsoa, ev).set_index("short_name")
    assert c.loc["Beta", "population"] == 600
    assert c.loc["Alpha", "lsoas"] == 2
    assert c.loc["Gamma", "population"] == 0
    assert list(c.index) == ["Beta", "Alpha", "Gamma"]


def test_catchments_rejects_unknown_events(toy_lsoa):
    ev = _events_bng([("Alpha", 0, 0)])
    with pytest.raises(ValueError, match="Beta"):
        lp.catchments(toy_lsoa, ev)


# Task 9: Shape functions — founding order, names, extremes
def test_id_order_check_spearman():
    ev = pd.DataFrame({"short_name": ["A", "B", "C", "D"], "id": [1, 2, 50, 40]})
    known = pd.DataFrame({"short_name": ["A", "B", "C", "X"],
                          "first_event": ["2004-10-02", "2007-01-01", "2010-05-01", "2011-01-01"],
                          "source": ["u1", "u2", "u3", "u4"]})
    table, rho = lp.id_order_check(ev, known)
    assert list(table["short_name"]) == ["A", "B", "C"]
    assert rho == pytest.approx(1.0)


def test_name_terms():
    ev = pd.DataFrame({"short_name": ["Bushy Park", "Wimbledon Common", "Bromley", "Hilly Fields",
                                      "Thames Path, Woolwich", "Finsbury Park"]})
    t = lp.name_terms(ev)
    assert t["Park"] == 2
    assert t["(place name only)"] == 1
    assert t["Path"] == 1 and t["Common"] == 1 and t["Fields"] == 1


def test_event_extremes():
    ev = _events_bng([("A", 0, 0), ("B", 100, 0), ("C", 5000, 0), ("D", 5300, 0)])
    x = lp.event_extremes(ev)
    assert x["closest_pair"] == ("A", "B")
    assert x["closest_m"] == pytest.approx(100)
    assert x["most_isolated"] == "C"
    assert x["isolated_nn_m"] == pytest.approx(300)


# Task 10: London alphabet route
def test_first_letter_and_missing():
    assert lp.first_letter("The Mystery") == "M"
    assert lp.first_letter("bushy park") == "B"
    ev = pd.DataFrame({"short_name": ["Alpha", "Bravo", "The Charlie"]})
    missing = lp.missing_letters(ev)
    assert "A" not in missing and "C" not in missing and "Z" in missing and len(missing) == 23


def test_alphabet_route_one_per_letter_and_short():
    ev = _events_bng([("Apple", 0, 0), ("Banana", 10, 0), ("Cherry", 20, 0),
                      ("Blueberry", 1000, 1000), ("Avocado", 2000, 0)])
    route = lp.alphabet_route(ev)
    assert sorted(lp.first_letter(n) for n in route) == ["A", "B", "C"]
    assert set(route) == {"Apple", "Banana", "Cherry"}
    assert lp.path_length(ev, route) == pytest.approx(20)


def test_alphabet_route_beats_alphabetical_order():
    rng = np.random.default_rng(0)
    names = [f"{chr(65 + i)}{k}" for i in range(8) for k in range(2)]
    ev = _events_bng([(n, *rng.uniform(0, 10_000, 2)) for n in names])
    route = lp.alphabet_route(ev)
    naive = [f"{chr(65 + i)}0" for i in range(8)]
    assert len(route) == 8
    assert lp.path_length(ev, route) < lp.path_length(ev, naive)


# Task 11: Where should the next parkrun go?
def test_candidate_sites_filters_function_size_and_existing():
    boundary = gpd.GeoDataFrame(geometry=[box(0, 0, 20_000, 20_000)], crs=lp.BNG)
    gs = gpd.GeoDataFrame({
        "id": ["big", "small", "golf", "near", "outside"],
        "function": ["Public Park Or Garden", "Playing Field", "Golf Course", "Public Park Or Garden", "Playing Field"],
        "name": ["Big", "Small", "Golf", "Near", "Out"],
    }, geometry=[box(1000, 1000, 1400, 1400), box(5000, 5000, 5100, 5100), box(8000, 8000, 8500, 8500),
                 box(15000, 15000, 15400, 15400), box(30000, 30000, 30400, 30400)], crs=lp.BNG)
    ev = _events_bng([("Existing", 15200, 15600)])
    out = lp.candidate_sites(gs, boundary, ev)
    assert list(out["id"]) == ["big"]
    assert out["area_ha"].iloc[0] == pytest.approx(16)


def test_best_new_sites_greedy_coverage():
    lsoa = gpd.GeoDataFrame({"lsoa21cd": ["far1", "far2", "near"], "population": [100, 10, 500],
                             "dist_m": [4000.0, 4000.0, 500.0]},
                            geometry=[box(0, 0, 10, 10), box(10_000, 0, 10_010, 10), box(5000, 0, 5010, 10)], crs=lp.BNG)
    cands = gpd.GeoDataFrame({"function": ["Playing Field", "Playing Field"], "name": ["X", "Y"], "area_ha": [12.0, 30.0]},
                             geometry=[box(0, 0, 50, 50), box(10_000, 0, 10_050, 50)], crs=lp.BNG)
    out = lp.best_new_sites(cands, lsoa, k=3)
    assert list(out["site"]) == ["X", "Y"]
    assert list(out["added_population"]) == [100, 10]
