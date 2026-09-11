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
