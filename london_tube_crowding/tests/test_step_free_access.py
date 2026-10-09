from pathlib import Path
from zipfile import ZipFile

import pandas as pd

import step_free_access as access


def test_load_topology_tables_reads_requested_csv_members(tmp_path: Path):
    archive_path = tmp_path / "topology.zip"
    with ZipFile(archive_path, "w") as archive:
        archive.writestr(
            "PlatformServices.csv",
            "PlatformUniqueId,StopAreaNaptanCode,Line,MinStep\n"
            "platform-a,940GZZLUACT,district,\n",
        )
        archive.writestr(
            "StepFreeIntechangeInfo.csv",
            "FromPlatformUniqueId,ToPlatformUniqueId,DistanceInMetres\n"
            "platform-a,platform-b,75\n",
        )

    tables = access.load_topology_tables(archive_path)

    assert tables["PlatformServices"].loc[0, "StopAreaNaptanCode"] == "940GZZLUACT"
    assert tables["PlatformServices"].loc[0, "MinStep"] == ""
    assert tables["StepFreeIntechangeInfo"].loc[0, "DistanceInMetres"] == "75"


def test_build_platform_service_table_joins_without_collapsing_services():
    station_master = pd.DataFrame(
        [
            {
                "naptan": "940GZZLUACT",
                "name": "Acton Town",
                "tube_lines": "district;piccadilly",
                "hub_naptan_code": "",
            }
        ]
    )
    platform_services = pd.DataFrame(
        [
            {
                "PlatformUniqueId": "acton-district-east",
                "StopAreaNaptanCode": "940GZZLUACT",
                "Line": "district",
                "DirectionTowards": "Upminster",
                "MinStep": "80",
                "MaxStep": "120",
                "AverageStep": "100",
                "MinGap": "50",
                "MaxGap": "90",
                "AverageGap": "70",
                "DesignatedLevelAccessPoint": "TRUE",
                "LevelAccessByManualRamp": "TRUE",
                "AdditionalAccessibilityInformation": "Use marked boarding point",
            },
            {
                "PlatformUniqueId": "acton-piccadilly-west",
                "StopAreaNaptanCode": "940GZZLUACT",
                "Line": "piccadilly",
                "DirectionTowards": "Uxbridge",
                "MinStep": "",
                "MaxStep": "",
                "AverageStep": "",
                "MinGap": "",
                "MaxGap": "",
                "AverageGap": "",
                "DesignatedLevelAccessPoint": "FALSE",
                "LevelAccessByManualRamp": "False",
                "AdditionalAccessibilityInformation": "",
            },
            {
                "PlatformUniqueId": "outside-london",
                "StopAreaNaptanCode": "910GZ999999",
                "Line": "national-rail",
                "DirectionTowards": "Elsewhere",
                "MinStep": "",
                "MaxStep": "",
                "AverageStep": "",
                "MinGap": "",
                "MaxGap": "",
                "AverageGap": "",
                "DesignatedLevelAccessPoint": "FALSE",
                "LevelAccessByManualRamp": "False",
                "AdditionalAccessibilityInformation": "",
            },
        ]
    )

    result = access.build_platform_service_table(platform_services, station_master)

    assert len(result) == 2
    assert result["station_naptan"].tolist() == ["940GZZLUACT", "940GZZLUACT"]
    assert result["station_name"].tolist() == ["Acton Town", "Acton Town"]
    assert result["line"].tolist() == ["district", "piccadilly"]
    assert result.loc[1, "max_step"] == ""
    assert result.loc[0, "level_access_by_manual_ramp"] == "TRUE"


def test_load_lift_disruptions_matches_naptan_and_hub_and_keeps_duplicates(tmp_path: Path):
    station_master = pd.DataFrame(
        [
            {"naptan": "940GZZLUACT", "name": "Acton Town", "hub_naptan_code": ""},
            {"naptan": "940GZZLUAMS", "name": "Amersham", "hub_naptan_code": "HUBAMR"},
        ]
    )
    snapshot_path = tmp_path / "lifts.json"
    snapshot_path.write_text(
        '[{"stationUniqueId":"940GZZLUACT",'
        '"disruptedLiftUniqueIds":["lift-a"],"message":"Lift unavailable"},'
        '{"stationUniqueId":"HUBAMR",'
        '"disruptedLiftUniqueIds":["lift-b","lift-c"],"message":"Use other entrance"},'
        '{"stationUniqueId":"HUBAMR",'
        '"disruptedLiftUniqueIds":["lift-b"],"message":"Platform access affected"},'
        '{"stationUniqueId":"HUBUNKNOWN",'
        '"disruptedLiftUniqueIds":[],"message":"Unmatched station"}]',
        encoding="utf-8",
    )

    result = access.load_lift_disruptions(snapshot_path, station_master)

    assert len(result) == 4
    assert result["station_naptan"].tolist() == [
        "940GZZLUACT",
        "940GZZLUAMS",
        "940GZZLUAMS",
        "",
    ]
    assert result["station_name"].tolist() == [
        "Acton Town",
        "Amersham",
        "Amersham",
        "",
    ]
    assert result["lift_ids"].tolist() == ["lift-a", "lift-b;lift-c", "lift-b", ""]
    assert result["matched_tube_station"].tolist() == [True, True, True, False]