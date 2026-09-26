import importlib.util
from pathlib import Path

MODULE_PATH = Path(__file__).resolve().parents[1] / "london_tube_crowding.py"
SPEC = importlib.util.spec_from_file_location("tube_module", MODULE_PATH)
assert SPEC is not None and SPEC.loader is not None
module = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(module)

build_station_catalog = module.build_station_catalog
extract_time_series = module.extract_time_series
parse_station_payload = module.parse_station_payload
canonical_station_naptans = module.canonical_station_naptans
extract_line_flow_rows = module.extract_line_flow_rows
extract_train_loading_rows = module.extract_train_loading_rows


def _crowding_payload():
    return {
        "naptanId": "940GZZLUACT",
        "commonName": "Acton Town Underground Station",
        "lines": [
            {
                "id": "district",
                "name": "District",
                "crowding": {
                    # TfL returns several unlabeled components per slice, in no fixed order.
                    "passengerFlows": [
                        {"timeSlice": "0815-0830", "value": 69},
                        {"timeSlice": "0800-0815", "value": 14},
                        {"timeSlice": "0815-0830", "value": 4},
                        {"timeSlice": "0800-0815", "value": 4},
                        {"timeSlice": "0815-0830", "value": 10},
                    ],
                    "trainLoadings": [
                        {"line": "District", "lineDirection": "WB", "platformDirection": "WB",
                         "direction": "Inbound", "naptanTo": "940GZZLUECM", "timeSlice": "0815-0830", "value": 1},
                        {"line": "District", "lineDirection": "EB", "platformDirection": "EB",
                         "direction": "Outbound", "naptanTo": "940GZZLUCWP", "timeSlice": "0815-0830", "value": 3},
                    ],
                },
            },
            {"id": "piccadilly", "name": "Piccadilly", "crowding": {}},
        ],
    }


def test_extract_line_flow_rows_sums_unlabeled_components_per_slice():
    rows = extract_line_flow_rows(_crowding_payload(), "940GZZLUACT", "Acton Town", "district")
    by_slice = {r["time_slice"]: r for r in rows}
    assert len(rows) == 2
    assert by_slice["0815-0830"]["value"] == 83
    assert by_slice["0815-0830"]["n_components"] == 3
    assert by_slice["0800-0815"]["value"] == 18
    assert by_slice["0800-0815"]["n_components"] == 2
    assert all(r["line"] == "district" for r in rows)


def test_extract_train_loading_rows_keeps_direction_and_next_station():
    rows = extract_train_loading_rows(_crowding_payload(), "940GZZLUACT", "Acton Town", "district")
    assert len(rows) == 2
    outbound = next(r for r in rows if r["direction"] == "Outbound")
    assert outbound == {
        "station_naptan": "940GZZLUACT",
        "common_name": "Acton Town",
        "line": "district",
        "direction": "Outbound",
        "line_direction": "EB",
        "naptan_to": "940GZZLUCWP",
        "time_slice": "0815-0830",
        "value": 3,
    }


def test_canonical_station_naptans_ignores_platform_stop_points():
    catalog = [
        {"station_naptan": "940GZZLUCWR"},
        {"station_naptan": "9400ZZLUCWR1"},
        {"station_naptan": "940GZZLUWPL"},
        {"station_naptan": "9400ZZLUWPL3"},
        {"station_naptan": "940GZZBPSUST"},
    ]
    result = canonical_station_naptans(catalog)
    assert result == ["940GZZLUCWR", "940GZZLUWPL", "940GZZBPSUST"]


def test_build_station_catalog_resolves_unique_station_line_ids(monkeypatch):
    station_rows = [
        {
            "stopType": "NaptanMetroEntrance",
            "stationNaptan": "940GZZLUAMS",
            "naptanId": "0400ZZLUAMS0",
            "commonName": "Amersham Underground Station",
            "modes": ["tube"],
            "lat": 51.67,
            "lon": -0.60,
        },
        {
            "stopType": "NaptanMetroEntrance",
            "stationNaptan": "940GZZLUAMS",
            "naptanId": "0400ZZLUAMS1",
            "commonName": "Amersham Underground Station",
            "modes": ["tube"],
            "lat": 51.67,
            "lon": -0.60,
        },
    ]

    def fake_fetch_tube_station_list():
        return station_rows

    def fake_detail_fetch(station_id):
        assert station_id == "940GZZLUAMS"
        return {
            "stationNaptan": "940GZZLUAMS",
            "commonName": "Amersham Underground Station",
            "stopType": "NaptanMetroStation",
            "modes": ["tube"],
            "lines": [{"id": "metropolitan", "name": "Metropolitan"}],
            "lat": 51.67,
            "lon": -0.60,
        }

    monkeypatch.setattr(module, "fetch_tube_station_list", fake_fetch_tube_station_list)
    monkeypatch.setattr(module, "fetch_station_detail", fake_detail_fetch)

    catalog = build_station_catalog(live=True)
    assert len(catalog) == 1
    assert catalog[0]["station_naptan"] == "940GZZLUAMS"
    assert catalog[0]["line_ids"] == "metropolitan"
    assert catalog[0]["common_name"] == "Amersham Underground Station"


def test_build_station_catalog_requires_explicit_live_fetch():
    try:
        build_station_catalog()
        assert False, "build_station_catalog() should refuse to hit the live API unless live=True"
    except RuntimeError as exc:
        assert "live=True" in str(exc)


def test_parse_station_payload_extracts_flow_series():
    payload = {
        "$type": "Tfl.Api.Presentation.Entities.StopPoint, Tfl.Api.Presentation.Entities",
        "naptanId": "940GZZLUGDG",
        "stationNaptan": "940GZZLUGDG",
        "commonName": "Green Park Underground Station",
        "lines": [
            {
                "$type": "Tfl.Api.Presentation.Entities.Identifier, Tfl.Api.Presentation.Entities",
                "id": "northern",
                "name": "Northern",
                "crowding": {
                    "$type": "Tfl.Api.Presentation.Entities.Crowding, Tfl.Api.Presentation.Entities",
                    "passengerFlows": [
                        {"timeSlice": "0700-0715", "value": 120},
                        {"timeSlice": "0745-0800", "value": 216},
                        {"timeSlice": "1700-1715", "value": 289},
                    ],
                },
            }
        ],
    }

    station = parse_station_payload(payload)
    assert station["naptanId"] == "940GZZLUGDG"
    assert station["commonName"] == "Green Park Underground Station"
    assert station["line_names"] == ["Northern"]
    assert station["crowding_by_line"]["Northern"]["0700-0715"] == 120
    assert station["crowding_by_line"]["Northern"]["1700-1715"] == 289

    series = extract_time_series(station)
    assert series["time_slice"].tolist() == ["0700-0715", "0745-0800", "1700-1715"]
    assert series["value"].tolist() == [120, 216, 289]
