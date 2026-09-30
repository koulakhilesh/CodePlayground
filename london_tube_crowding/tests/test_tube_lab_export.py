import json

import pandas as pd
import pytest

from tube_lab_export import build_tube_day, day_order

KM_LAT = 1 / 111  # one km of latitude, matching export_charts.py


def _crowding():
    rows = [
        ("940GZZA", "Alpha", "central", "0500-0515", 10),
        ("940GZZA", "Alpha", "victoria", "0500-0515", 5),
        ("940GZZA", "Alpha", "central", "0000-0015", 7),
        ("940GZZA", "Alpha", "central", "2345-0000", 3),
        ("940GZZB", "Beta", "central", "0500-0515", 1),
        ("940GZZC", "Beta", "district", "2345-0000", 2),
    ]
    return pd.DataFrame(rows, columns=["station_naptan", "common_name", "line", "time_slice", "value"])


def _master():
    return pd.DataFrame({
        "naptan": ["940GZZA", "940GZZB", "940GZZC"],
        "lat": [51.5074, 51.5074 + KM_LAT, 51.5074 + 3 * KM_LAT],
        "lon": [-0.1278, -0.1278, -0.1278],
    })


def test_day_order_starts_at_five():
    assert day_order(["0000", "0500", "2345", "0015"]) == ["0500", "2345", "0000", "0015"]


def test_slices_run_from_five_through_midnight():
    assert build_tube_day(_crowding(), _master())["slices"] == ["05:00", "23:45", "00:00"]


def test_lines_are_summed_and_missing_slices_are_zero():
    by = {s["n"]: s for s in build_tube_day(_crowding(), _master())["stations"]}
    assert by["Alpha"]["v"] == [15, 3, 7]
    assert by["Beta"]["v"] == [1, 2, 0]


def test_lines_and_distance_per_station_name():
    by = {s["n"]: s for s in build_tube_day(_crowding(), _master())["stations"]}
    assert by["Alpha"]["l"] == ["central", "victoria"]
    assert by["Beta"]["l"] == ["central", "district"]
    assert by["Alpha"]["km"] == 0.0
    assert by["Beta"]["km"] == 2.0


def test_output_is_sorted_and_json_safe():
    data = build_tube_day(_crowding(), _master())
    assert [s["n"] for s in data["stations"]] == ["Alpha", "Beta"]
    assert all(isinstance(v, int) for s in data["stations"] for v in s["v"])
    json.dumps(data, allow_nan=False)


def test_station_without_coordinates_is_named_in_the_error():
    master = _master()[lambda m: m["naptan"] != "940GZZA"]
    with pytest.raises(ValueError, match="Alpha"):
        build_tube_day(_crowding(), master)
