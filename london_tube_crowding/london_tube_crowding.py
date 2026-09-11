from __future__ import annotations

import csv
import json
import os
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests


TF_L_API = "https://api.tfl.gov.uk"


def _load_tfl_credentials() -> tuple[str | None, str | None]:
    """Read TfL credentials from environment or a local .env file."""
    app_id = os.getenv("TFL_APP_ID") or os.getenv("APP_ID")
    app_key = os.getenv("TFL_API_KEY") or os.getenv("APP_KEY") or os.getenv("TFL_APP_KEY")

    if app_key or app_id:
        return app_id, app_key

    env_path = Path(__file__).resolve().with_name(".env")
    if env_path.exists():
        for line in env_path.read_text(encoding="utf-8").splitlines():
            if not line or line.strip().startswith("#"):
                continue
            if "=" not in line:
                continue
            key, value = [part.strip() for part in line.split("=", 1)]
            if key == "TFL_APP_ID" or key == "APP_ID":
                app_id = value.strip('"\'')
            elif key in {"TFL_API_KEY", "APP_KEY", "TFL_APP_KEY"}:
                app_key = value.strip('"\'')

    return app_id, app_key


def _add_tfl_auth(params: dict[str, Any] | None = None) -> dict[str, Any]:
    """Attach the current TfL auth parameters to a request without clobbering caller-supplied values."""
    final_params = dict(params or {})
    app_id, app_key = _load_tfl_credentials()
    if app_id:
        final_params.setdefault("app_id", app_id)
    if app_key:
        final_params.setdefault("app_key", app_key)
    return final_params


def _get_json_with_retry(url: str, *, params: dict[str, Any] | None = None, user_agent: str = "Mozilla/5.0", max_retries: int = 7, base_delay: float = 1.0) -> Any:
    """Call a TfL endpoint with retry/backoff for transient 429/5xx responses."""
    last_error: Exception | None = None
    request_params = _add_tfl_auth(params)
    for attempt in range(max_retries):
        try:
            response = requests.get(url, params=request_params, timeout=60, headers={"User-Agent": user_agent})
            if response.status_code == 429:
                retry_after = response.headers.get("Retry-After")
                delay = float(retry_after) if retry_after is not None else base_delay * (2 ** attempt)
                time.sleep(delay)
                continue
            if response.status_code >= 500:
                time.sleep(base_delay * (2 ** attempt))
                continue
            response.raise_for_status()
            return response.json()
        except requests.RequestException as exc:
            last_error = exc
            if attempt == max_retries - 1:
                break
            time.sleep(base_delay * (2 ** attempt))
    if last_error is not None:
        raise last_error
    raise RuntimeError(f"Failed to fetch {url}")


def fetch_tube_station_list() -> list[dict[str, Any]]:
    """Fetch the raw list of Tube stop-point records from TfL."""
    url = f"{TF_L_API}/StopPoint/Mode/tube"
    payload = _get_json_with_retry(url)
    return payload.get("stopPoints", [])


def fetch_station_detail(station_id: str) -> dict[str, Any]:
    """Fetch a single stop-point detail payload with the line list for a station."""
    url = f"{TF_L_API}/StopPoint/{station_id}"
    data = _get_json_with_retry(url)
    if isinstance(data, dict) and data.get("httpStatus") == "NotFound":
        raise ValueError(f"Station not found: {station_id}")
    return data


def canonical_station_naptans(station_rows: list[dict[str, Any]] | pd.DataFrame) -> list[str]:
    """Return only canonical station-level TfL NaPTAN IDs.

    Platform stop points use platform suffixes such as 9400ZZLUCWR1 and are not valid
    station crowding IDs. Station crowding is only available for the canonical station ID
    pattern, which uses the 940GZZ prefix.
    """
    records = station_rows.to_dict(orient="records") if isinstance(station_rows, pd.DataFrame) else station_rows
    ids: list[str] = []
    seen: set[str] = set()
    for row in records:
        station_id = str(
            row.get("station_naptan")
            or row.get("stationNaptan")
            or row.get("naptan_id")
            or row.get("naptanId")
            or ""
        ).strip()
        if not station_id or station_id in seen:
            continue
        if not station_id.startswith("940GZZ"):
            continue
        seen.add(station_id)
        ids.append(station_id)
    return ids


def build_station_catalog(*, live: bool = False, limit: int | None = None) -> list[dict[str, Any]]:
    """Return a deduplicated station catalog with key metadata for analysis.

    The mode=tube endpoint contains entrance records as well as station records and
    many duplicates. We collapse by `stationNaptan`, then fetch the per-station
    detail endpoint to get the served lines for the real station-level record.

    The live TfL fetch is intentionally opt-in because the API is rate-limited and
    can stall analysis when called in default exploratory workflows.
    """
    if not live:
        raise RuntimeError(
            "Live TfL station fetch is disabled by default to prevent hangs. "
            "Call build_station_catalog(live=True) explicitly to refresh the catalog."
        )

    catalog: list[dict[str, Any]] = []
    seen: set[str] = set()
    for station in fetch_tube_station_list():
        raw_naptan = station.get("stationNaptan") or station.get("naptanId")
        if not raw_naptan:
            continue
        naptan = raw_naptan.strip()
        if not naptan or naptan in seen:
            continue
        if not naptan.startswith("940GZZ"):
            continue
        seen.add(naptan)

        detail = fetch_station_detail(naptan)
        time.sleep(0.25)
        line_ids = [
            line.get("id") or line.get("name")
            for line in detail.get("lines") or []
            if (line.get("id") or line.get("name"))
        ]

        catalog.append({
            "naptan_id": detail.get("stationNaptan") or naptan,
            "station_naptan": detail.get("stationNaptan") or naptan,
            "naptan_id_legacy": detail.get("naptanId") or station.get("naptanId"),
            "common_name": detail.get("commonName") or station.get("commonName"),
            "indicator": station.get("indicator") or detail.get("indicator"),
            "stop_type": detail.get("stopType") or station.get("stopType"),
            "modes": ";".join(detail.get("modes") or station.get("modes") or []),
            "line_ids": ";".join(line_ids),
            "lat": detail.get("lat") or station.get("lat"),
            "lon": detail.get("lon") or station.get("lon"),
            "hub_naptan_code": detail.get("hubNaptanCode") or station.get("hubNaptanCode"),
        })

        if limit is not None and len(catalog) >= limit:
            break
    return catalog


def export_station_catalog_csv(output_path: str | Path, *, live: bool = False, limit: int | None = None) -> Path:
    """Write the live TfL station catalog to CSV."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)
    rows = build_station_catalog(live=live, limit=limit)
    fieldnames = [
        "naptan_id",
        "station_naptan",
        "naptan_id_legacy",
        "common_name",
        "indicator",
        "stop_type",
        "modes",
        "line_ids",
        "lat",
        "lon",
        "hub_naptan_code",
    ]
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for row in rows:
            writer.writerow({key: row.get(key) for key in fieldnames})
    return output


def parse_station_payload(payload: dict[str, Any]) -> dict[str, Any]:
    """Extract the station metadata and the crowding time series for each line."""
    naptan_id = payload.get("naptanId") or payload.get("stationNaptan")
    common_name = payload.get("commonName")
    line_entries = payload.get("lines") or []

    crowding_by_line: dict[str, dict[str, int]] = {}
    line_names: list[str] = []

    for line in line_entries:
        line_name = line.get("name") or line.get("id")
        if not line_name:
            continue
        line_names.append(line_name)
        crowding = line.get("crowding") or {}
        flows = crowding.get("passengerFlows") or []
        values: dict[str, int] = {}
        for flow in flows:
            ts = flow.get("timeSlice")
            val = flow.get("value")
            if ts is not None and val is not None:
                values[str(ts)] = int(val)
        crowding_by_line[line_name] = values

    return {
        "naptanId": naptan_id,
        "commonName": common_name,
        "line_names": line_names,
        "crowding_by_line": crowding_by_line,
    }


def extract_time_series(station: dict[str, Any]) -> pd.DataFrame:
    """Flatten a station's crowding to a single time-slice series."""
    rows: list[dict[str, Any]] = []
    for line_name, by_slice in station.get("crowding_by_line", {}).items():
        for time_slice, value in by_slice.items():
            rows.append({
                "line": line_name,
                "time_slice": time_slice,
                "value": value,
            })
    df = pd.DataFrame(rows)
    if df.empty:
        return pd.DataFrame(columns=["line", "time_slice", "value"])
    return df.sort_values(["line", "time_slice"]).reset_index(drop=True)


def fetch_station_crowding(station_id: str, line_name: str | None = None) -> dict[str, Any]:
    """Fetch crowding for a given station and optional line.

    The TfL API route is: /StopPoint/{id}/Crowding/{line}?direction=all
    where the line must match one of the station's served lines.
    """
    if line_name is None:
        station_list = fetch_tube_station_list()
        for station in station_list:
            if station.get("naptanId") == station_id or station.get("stationNaptan") == station_id:
                line_name = station.get("lines", [{}])[0].get("id")
                break
        if line_name is None:
            raise ValueError(f"No line found for station {station_id}")

    url = f"{TF_L_API}/StopPoint/{station_id}/Crowding/{line_name}"
    params = {"direction": "all"}
    data = _get_json_with_retry(url, params=params)
    if isinstance(data, dict) and data.get("httpStatus") == "NotFound":
        raise ValueError(f"Crowding not found for {station_id} on {line_name}: {data.get('message')}")
    return data


def export_station_csv(stations: list[dict[str, Any]], output_path: str | Path) -> Path:
    """Write a flat station table to CSV."""
    output = Path(output_path)
    output.parent.mkdir(parents=True, exist_ok=True)

    fieldnames = ["naptanId", "commonName", "line_names", "crowding_by_line"]
    with output.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        for station in stations:
            writer.writerow({
                "naptanId": station.get("naptanId"),
                "commonName": station.get("commonName"),
                "line_names": ";".join(station.get("line_names", [])),
                "crowding_by_line": str(station.get("crowding_by_line", {})),
            })
    return output


def extract_line_flow_rows(payload: dict[str, Any], station_id: str, station_name: str | None = None, line_name: str | None = None) -> list[dict[str, Any]]:
    """Flatten a TfL crowding payload into one row per station-line-time-slice."""
    if not isinstance(payload, dict):
        return []

    if line_name is None:
        station_name = payload.get("commonName") or station_name
        lines = payload.get("lines") or []
        rows: list[dict[str, Any]] = []
        for line in lines:
            rows.extend(extract_line_flow_rows(payload, station_id, station_name, line.get("id") or line.get("name")))
        return rows

    lines = payload.get("lines") or []
    selected = None
    for line in lines:
        if (line.get("id") or line.get("name")) == line_name:
            selected = line
            break
    if selected is None and payload.get("stationNaptan") == station_id:
        selected = payload

    crowding = (selected or {}).get("crowding") or payload.get("crowding") or {}
    flows = crowding.get("passengerFlows") or []

    rows: list[dict[str, Any]] = []
    for flow in flows:
        time_slice = flow.get("timeSlice")
        value = flow.get("value")
        if time_slice is None or value is None:
            continue
        rows.append({
            "station_naptan": station_id,
            "common_name": station_name or payload.get("commonName") or payload.get("stationName"),
            "line": line_name,
            "time_slice": str(time_slice),
            "value": int(value),
        })
    return rows


def build_station_crowding_dataset(
    catalog_path: str | Path = "data/tube_station_catalog.csv",
    output_dir: str | Path = "data/tube_crowding",
    *,
    live: bool = False,
    limit: int | None = None,
    sleep_seconds: float = 0.35,
) -> Path:
    """Fetch live TfL crowding for station/line combinations and save them locally.

    Live fetches are opt-in because the API is rate-limited and can stall analysis in
    exploratory workflows. For everyday EDA, the workflow should read the cached CSV rather
    than re-hit the API.
    """
    if not live:
        raise RuntimeError(
            "Live TfL crowding fetch is disabled by default to prevent hangs. "
            "Call build_station_crowding_dataset(live=True, limit=...) explicitly."
        )

    catalog_path = Path(catalog_path)
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    (output_path / "raw").mkdir(parents=True, exist_ok=True)

    if not catalog_path.exists():
        raise FileNotFoundError(f"Catalog CSV not found: {catalog_path}. Build it first with build_station_catalog(live=True).")

    catalog = pd.read_csv(catalog_path)
    catalog = catalog.fillna("")
    catalog = catalog[catalog["station_naptan"].astype(str).str.strip() != ""]
    catalog = catalog[catalog["station_naptan"].astype(str).str.startswith("940GZZ")].copy()

    rows: list[dict[str, Any]] = []
    for idx, row in catalog.iterrows():
        if limit is not None and idx >= limit:
            break
        station_id = str(row.get("station_naptan") or row.get("naptan_id") or "").strip()
        if not station_id:
            continue

        line_ids = [part.strip() for part in str(row.get("line_ids") or "").split(";") if part.strip()]
        if not line_ids:
            continue

        for line_name in line_ids:
            try:
                payload = fetch_station_crowding(station_id, line_name)
            except ValueError:
                continue
            except requests.RequestException:
                continue

            station_name = str(row.get("common_name") or row.get("station_name") or "").strip() or None
            extracted = extract_line_flow_rows(payload, station_id, station_name, line_name)
            rows.extend(extracted)

            raw_file = output_path / "raw" / f"{station_id}_{line_name}.json"
            raw_file.write_text(json.dumps(payload, indent=2), encoding="utf-8")
            time.sleep(sleep_seconds)

    csv_path = output_path / "station_line_crowding.csv"
    pd.DataFrame(rows).to_csv(csv_path, index=False)

    missing_station_path = output_path / "missing_station_audit.csv"
    catalog_ids = set(catalog["station_naptan"].astype(str).str.strip())
    crowding_ids = set(pd.DataFrame(rows)["station_naptan"].astype(str).str.strip()) if rows else set()
    missing_ids = sorted(catalog_ids - crowding_ids)
    pd.DataFrame({
        "station_naptan": missing_ids,
        "status": ["missing_from_crowding_dataset"] * len(missing_ids),
    }).to_csv(missing_station_path, index=False)
    return csv_path


if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Create a local crowding CSV from TfL data.")
    parser.add_argument("--live", action="store_true", help="Opt in to the live TfL network fetch")
    parser.add_argument("--limit", type=int, default=None, help="Optional max number of catalog rows to fetch")
    parser.add_argument("--sleep", type=float, default=11.0, help="Seconds to wait between live API calls to respect rate limits")
    args = parser.parse_args()

    if not args.live:
        raise SystemExit(
            "Live fetch disabled by default. Re-run with --live to refresh the data, or use the cached local CSV for EDA."
        )

    catalog_path = Path("data/tube_station_catalog.csv")
    if not catalog_path.exists():
        export_station_catalog_csv(catalog_path, live=True)

    output = build_station_crowding_dataset(catalog_path, live=True, limit=args.limit, sleep_seconds=args.sleep)
    print(f"Saved crowding dataset to {output}")
