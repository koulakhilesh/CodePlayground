import plotly.graph_objects as go
import pytest

from export_wren_charts import SOURCES, cite, fate, grid_to_lonlat, spread


def test_every_chart_source_names_a_licence():
    assert all("CC BY-SA" in text or "OGL" in text for text in SOURCES.values())


def test_cite_wraps_source_and_makes_room():
    fig = cite(go.Figure(layout=dict(margin=dict(b=50))), "word " * 30, width=40)
    note = fig.layout.annotations[0]
    assert note.text.count("<br>") == 3 and fig.layout.margin.b == 50 + 14 * 4 + 10


def test_spread_offsets_only_close_years():
    assert spread(2, [1868, 1870, 1872, 1873, 1890]) == [2, 2.24, 1.76, 2.12, 2]


def test_grid_reference_converts_to_known_location():
    lon, lat = grid_to_lonlat("TQ 15867 74115")
    assert lat == pytest.approx(51.4542, abs=0.0005) and lon == pytest.approx(-0.3338, abs=0.0005)


@pytest.mark.parametrize("section,cohort,lost,expected", [
    ("Tower remaining", "parish_replacement", True, "tower only"),
    ("Substantially rebuilt after the Blitz", "parish_replacement", False, "standing"),
    ("Churches built outside the City of London", "outside_fire_area", True, "gone"),
    ("Demolished due to the Union of Benefices Act (chronological order)", "parish_replacement", True, "gone"),
    ("Survived in original form", "cathedral", False, "standing"),
])
def test_fate_follows_section_and_body_loss(section, cohort, lost, expected):
    assert fate(section, cohort, lost) == expected
