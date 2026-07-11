"""Scrape English Heritage London blue plaques into a dated CSV.

Two-pass and resumable:
  1. List pass  — the JSON API returns name/dates/professions/address/path.
  2. Detail pass — each plaque's HTML page adds category, inscription, material,
     coordinates, and a biography paragraph.

TLS verification is intentionally disabled: this personal project runs behind a
corporate TLS-intercepting proxy and only reads public data (no credentials).
See PROBE_NOTES.md for the full field mapping.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import time
import warnings
from datetime import date
from pathlib import Path

import pandas as pd
import requests
import urllib3
from bs4 import BeautifulSoup

BASE = "https://www.english-heritage.org.uk"
LIST_API = f"{BASE}/api/BluePlaqueSearch/GetMatchingBluePlaques"
USER_AGENT = "koulakhilesh-blueplaques-scraper (personal analysis)"
REQUEST_DELAY_S = 0.7
VERIFY_TLS = False  # corporate proxy intercepts TLS; reading public data only

_PROJECT_DIR = Path(__file__).resolve().parent
_DATA_DIR = _PROJECT_DIR.parent / "data"
CACHE_DIR = _DATA_DIR / ".cache" / "plaques"

# Silence the expected "unverified HTTPS request" noise from the disabled verify.
warnings.simplefilter("ignore", urllib3.exceptions.InsecureRequestWarning)


# --------------------------------------------------------------------------- #
# Parsing (pure, network-free, unit-tested against saved fixtures)
# --------------------------------------------------------------------------- #

_DATES_RE = re.compile(r"\((?:b\.\s*)?(\d{4})?\s*[–-]\s*(\d{4})?\)")
_TRAILING_DATES_RE = re.compile(r"\s*\((?:b\.\s*)?\d{0,4}\s*[–-]?\s*\d{0,4}\)\s*$")


def _title_case_surname(surname: str) -> str:
    return " ".join(w.capitalize() for w in surname.split())


def parse_name_and_dates(title: str) -> tuple[str, int | None, int | None]:
    """Extract (display_name, born, died) from a list `title`.

    Person titles look like "ABERCROMBIE, Sir Patrick (1879-1957)".
    Place titles look like "14 BUCKINGHAM STREET" (kept as-is, no dates).
    """
    born = died = None
    m = _DATES_RE.search(title)
    if m:
        born = int(m.group(1)) if m.group(1) else None
        died = int(m.group(2)) if m.group(2) else None

    name = _TRAILING_DATES_RE.sub("", title).strip()
    if "," in name:
        surname, _, rest = name.partition(",")
        name = f"{rest.strip()} {_title_case_surname(surname.strip())}".strip()
    return name, born, died


def parse_borough(address: str | None) -> str | None:
    """The borough is the last comma-separated segment of the address."""
    if not address:
        return None
    return address.split(",")[-1].strip() or None


def parse_list_record(record: dict) -> dict:
    """Fields derivable from one list-API record (no network)."""
    name, born, died = parse_name_and_dates(record.get("title", "") or "")
    address = record.get("address")
    return {
        "id": record.get("id"),
        "name": name,
        "born": born,
        "died": died,
        "professions": record.get("professions"),
        "address": address,
        "borough": parse_borough(address),
        "summary": record.get("summary"),
        "detail_url": record.get("path"),
    }


def _panel_text(soup: BeautifulSoup, panel_id: str, value_class: str) -> str | None:
    panel = soup.find(id=f"ctl00_cpMain_BluePlaqueDetails_{panel_id}")
    if panel is None:
        return None
    p = panel.find("p", class_=value_class)
    return p.get_text(strip=True) if p else None


_COORDS_RE = re.compile(
    r'GetMapAndData\(\s*"blueplaquepage".*?"(?:[^"\\]|\\.)*"\s*,\s*'
    r"(-?\d+\.\d+)\s*,\s*(-?\d+\.\d+)",
    re.S,
)


def parse_detail_html(html: str) -> dict:
    """Fields derivable from one plaque's detail HTML page (no network)."""
    soup = BeautifulSoup(html, "html.parser")

    lat = lng = None
    m = _COORDS_RE.search(html)
    if m:
        lat, lng = float(m.group(1)), float(m.group(2))

    bio = None
    bio_div = soup.select_one("div.simple-content.pad3000")
    if bio_div:
        first_p = bio_div.find("p")
        if first_p:
            bio = first_p.get_text(strip=True)

    return {
        "profession_detail": _panel_text(soup, "pnlProfession", "large-profession"),
        "category": _panel_text(soup, "pnlCategory", "large-category"),
        "inscription": _panel_text(soup, "pnlInscription", "small-detail"),
        "material": _panel_text(soup, "pnlMaterial", "small-detail"),
        "lat": lat,
        "lng": lng,
        "biography": bio,
    }


def parse_plaque(record: dict, detail_html: str | None = None) -> dict:
    """Combine list-record and detail-HTML fields into one flat row."""
    row = parse_list_record(record)
    if detail_html:
        row.update(parse_detail_html(detail_html))
    return row


# --------------------------------------------------------------------------- #
# Fetching (network; resumable via on-disk cache)
# --------------------------------------------------------------------------- #

def _session() -> requests.Session:
    s = requests.Session()
    s.headers.update({"User-Agent": USER_AGENT})
    s.verify = VERIFY_TLS
    return s


def _get_with_retry(session: requests.Session, url: str, *, params=None,
                    max_retries: int = 4) -> requests.Response:
    last_exc: Exception | None = None
    for attempt in range(max_retries):
        try:
            resp = session.get(url, params=params, timeout=40)
        except requests.RequestException as exc:
            last_exc = exc
            time.sleep(REQUEST_DELAY_S * (2 ** attempt))
            continue
        if resp.status_code in (429, 500, 502, 503, 504):
            time.sleep(REQUEST_DELAY_S * (2 ** attempt))
            continue
        resp.raise_for_status()
        return resp
    if last_exc:
        raise last_exc
    resp.raise_for_status()
    return resp


def fetch_list_page(session: requests.Session, page: int, size: int = 100) -> dict:
    params = {"pageBP": page, "sizeBP": size, "borBP": 0, "keyBP": "", "catBP": 0}
    return _get_with_retry(session, LIST_API, params=params).json()


def iter_all_list_records(session: requests.Session, size: int = 100):
    page, seen, total = 1, 0, None
    while True:
        payload = fetch_list_page(session, page, size)
        total = payload.get("total", total)
        records = payload.get("plaques", [])
        if not records:
            break
        for rec in records:
            yield rec
            seen += 1
        if total is not None and seen >= total:
            break
        page += 1
        time.sleep(REQUEST_DELAY_S)


def _cache_path(key: str) -> Path:
    return CACHE_DIR / f"{hashlib.sha1(key.encode()).hexdigest()}.html"


def fetch_plaque_detail(session: requests.Session, record: dict) -> str:
    """Fetch (or read from cache) the detail HTML for one plaque."""
    CACHE_DIR.mkdir(parents=True, exist_ok=True)
    path = record.get("path") or ""
    url = path if path.startswith("http") else f"{BASE}{path}"
    cached = _cache_path(url)
    if cached.exists():
        return cached.read_text(encoding="utf-8")
    html = _get_with_retry(session, url).text
    cached.write_text(html, encoding="utf-8")
    time.sleep(REQUEST_DELAY_S)
    return html


# --------------------------------------------------------------------------- #
# Orchestration
# --------------------------------------------------------------------------- #

def scrape_all(limit: int | None = None) -> pd.DataFrame:
    session = _session()
    rows = []
    for i, record in enumerate(iter_all_list_records(session)):
        if limit is not None and i >= limit:
            break
        try:
            detail_html = fetch_plaque_detail(session, record)
        except requests.RequestException as exc:
            print(f"  detail failed for {record.get('id')}: {exc}")
            detail_html = None
        rows.append(parse_plaque(record, detail_html))
        if (i + 1) % 50 == 0:
            print(f"  ...{i + 1} plaques")
    return pd.DataFrame(rows)


def _write_csv(df: pd.DataFrame) -> Path:
    _DATA_DIR.mkdir(parents=True, exist_ok=True)
    out = _DATA_DIR / f"blue_plaques_{date.today():%Y-%m}.csv"
    df.to_csv(out, index=False)
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Scrape London blue plaques.")
    parser.add_argument("--limit", type=int, default=None,
                        help="Only scrape the first N plaques (smoke test).")
    args = parser.parse_args()

    df = scrape_all(limit=args.limit)
    out = _write_csv(df)
    print(f"Wrote {len(df)} rows to {out}")
    if args.limit is None and not (900 <= len(df) <= 1200):
        print(f"WARNING: expected ~1,036 rows, got {len(df)}")


if __name__ == "__main__":
    main()
