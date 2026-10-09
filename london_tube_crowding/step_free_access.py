from __future__ import annotations

import json
from pathlib import Path
from zipfile import ZipFile

import pandas as pd


def load_topology_tables(archive_path: Path) -> dict[str, pd.DataFrame]:
    """Read every CSV in TfL's detailed station topology archive as strings."""
    with ZipFile(archive_path) as archive:
        tables = {
            Path(member).stem: pd.read_csv(
                archive.open(member),
                dtype=str,
                keep_default_na=False,
            )
            for member in archive.namelist()
            if member.lower().endswith(".csv")
        }
    return tables


def build_platform_service_table(
    platform_services: pd.DataFrame,
    station_master: pd.DataFrame,
) -> pd.DataFrame:
    """Join platform service records to Tube stations without aggregating rows."""
    station_columns = station_master[["naptan", "name"]].drop_duplicates("naptan")
    joined = platform_services.merge(
        station_columns,
        how="inner",
        left_on="StopAreaNaptanCode",
        right_on="naptan",
        validate="many_to_one",
    )
    joined = joined.rename(
        columns={
            "PlatformUniqueId": "platform_unique_id",
            "naptan": "station_naptan",
            "name": "station_name",
            "Line": "line",
            "DirectionTowards": "direction_towards",
            "MinGap": "min_gap",
            "MaxGap": "max_gap",
            "AverageGap": "average_gap",
            "MinStep": "min_step",
            "MaxStep": "max_step",
            "AverageStep": "average_step",
            "DesignatedLevelAccessPoint": "designated_level_access_point",
            "LevelAccessByManualRamp": "level_access_by_manual_ramp",
            "AdditionalAccessibilityInformation": "additional_accessibility_information",
        }
    )
    output_columns = [
        "platform_unique_id",
        "station_naptan",
        "station_name",
        "line",
        "direction_towards",
        "min_gap",
        "max_gap",
        "average_gap",
        "min_step",
        "max_step",
        "average_step",
        "designated_level_access_point",
        "level_access_by_manual_ramp",
        "additional_accessibility_information",
    ]
    return joined[output_columns].reset_index(drop=True)


def load_lift_disruptions(
    snapshot_path: Path,
    station_master: pd.DataFrame,
) -> pd.DataFrame:
    """Normalize a dated TfL lift feed while preserving unmatched and duplicate records."""
    station_by_identifier: dict[str, tuple[str, str]] = {}
    for row in station_master.itertuples(index=False):
        station_by_identifier[row.naptan] = (row.naptan, row.name)
        hub_code = getattr(row, "hub_naptan_code", "")
        if hub_code:
            station_by_identifier.setdefault(hub_code, (row.naptan, row.name))

    with snapshot_path.open(encoding="utf-8") as source:
        records = json.load(source)

    normalized = []
    for record in records:
        station_identifier = record.get("stationUniqueId", "")
        station = station_by_identifier.get(station_identifier)
        lift_ids = record.get("disruptedLiftUniqueIds") or []
        normalized.append(
            {
                "station_unique_id": station_identifier,
                "station_naptan": station[0] if station else "",
                "station_name": station[1] if station else "",
                "lift_ids": ";".join(lift_ids),
                "message": record.get("message", ""),
                "matched_tube_station": station is not None,
            }
        )

    return pd.DataFrame(
        normalized,
        columns=[
            "station_unique_id",
            "station_naptan",
            "station_name",
            "lift_ids",
            "message",
            "matched_tube_station",
        ],
    )