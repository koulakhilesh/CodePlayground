import json

import pandas as pd

from plaques_lab_export import build_plaques, tidy_name


def _df():
    return pd.DataFrame({
        "name": ["14 BUCKINGHAM STREET", "Ira Aldridge", "No location", "  Samuel   Pepys "],
        "lat": [51.50773, 51.52, None, 51.51],
        "lng": [-0.12803, -0.10, -0.12, -0.13],
    })


def test_tidy_name():
    assert tidy_name("14 BUCKINGHAM STREET") == "14 Buckingham Street"
    assert tidy_name("Ira Aldridge") == "Ira Aldridge"
    assert tidy_name("  Samuel   Pepys ") == "Samuel Pepys"
    assert tidy_name(float("nan")) == ""


def test_rows_without_coordinates_are_dropped():
    data = build_plaques(_df())
    assert len(data["x"]) == len(data["y"]) == len(data["n"]) == 3
    assert data["n"] == ["14 Buckingham Street", "Ira Aldridge", "Samuel Pepys"]


def test_projected_to_british_national_grid_metres():
    data = build_plaques(_df())
    assert data["crs"] == "EPSG:27700"
    # pyproj's EPSG:4326 -> 27700 for this point; a wrong datum shift would be ~100 m off.
    assert abs(data["x"][0] - 530012) < 5
    assert abs(data["y"][0] - 180416) < 5
    assert all(isinstance(v, int) for v in data["x"] + data["y"])
    json.dumps(data, allow_nan=False)
