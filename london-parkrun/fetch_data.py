"""Download and unpack the raw data for the London parkrun analysis.

    python london-parkrun/fetch_data.py            # fetch missing files only
    python london-parkrun/fetch_data.py --refresh  # re-download everything
"""
from __future__ import annotations

import argparse
import shutil
import zipfile
from pathlib import Path

import requests

RAW = Path(__file__).resolve().parents[1] / "data" / "parkrun" / "raw"
SOURCES = {
    "events.json": "https://images.parkrun.com/events.json",
    "statistical-gis-boundaries-london.zip": "https://data.london.gov.uk/download/20od9/9ba8c833-6370-4b11-abdc-314aa020d5e0/statistical-gis-boundaries-london.zip",
    "LB_LSOA2021_shp.zip": "https://data.london.gov.uk/download/20od9/2a5e50ac-c22e-4d68-89e2-85f1e0ff9057/LB_LSOA2021_shp.zip",
    "census2021-ts007a.zip": "https://www.nomisweb.co.uk/output/census/2021/census2021-ts007a.zip",
    "census2021-ts045.zip": "https://www.nomisweb.co.uk/output/census/2021/census2021-ts045.zip",
    "ptal_lsoa2011.csv": "https://data.london.gov.uk/download/24rz6/77d9b319-931e-4090-bf8e-f578938bd352/LSOA2011%20AvPTAI2015.csv",
    "naptan.csv": "https://naptan.api.dft.gov.uk/v1/access-nodes?dataFormat=csv",
    "opgrsp_gb.zip": "https://api.os.uk/downloads/v1/products/OpenGreenspace/downloads?area=GB&format=GeoPackage&redirect",
}
UNZIP = ("statistical-gis-boundaries-london.zip", "LB_LSOA2021_shp.zip", "opgrsp_gb.zip")


def download(url: str, dest: Path) -> None:
    with requests.get(url, stream=True, timeout=300) as r:
        r.raise_for_status()
        with open(dest, "wb") as f:
            # iter_content undoes gzip transfer-encoding; r.raw would not (events.json is gzipped).
            for chunk in r.iter_content(1 << 20):
                f.write(chunk)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--refresh", action="store_true")
    args = ap.parse_args()
    RAW.mkdir(parents=True, exist_ok=True)
    downloaded = False
    for name, url in SOURCES.items():
        dest = RAW / name
        if dest.exists() and not args.refresh:
            continue
        download(url, dest)
        print("fetched", name)
        downloaded = True
    unz = RAW / "unz"
    # Compute should_extract before mkdir; clear on refresh to avoid permission errors
    should_extract = args.refresh or downloaded or not unz.exists()
    if args.refresh and unz.exists():
        shutil.rmtree(unz)
    if should_extract:
        unz.mkdir(parents=True, exist_ok=True)
        for name in UNZIP:
            with zipfile.ZipFile(RAW / name) as z:
                z.extractall(unz)
    print("ready:", RAW)


if __name__ == "__main__":
    main()
