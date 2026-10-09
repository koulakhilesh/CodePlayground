"""Context collections: the not-rebuilt parishes and their unions with Wren churches.

Sources: Wikipedia lists of churches not rebuilt after the fire, the City of London census table
and the Monument article (CC BY-SA 4.0); Parentalia (1750), public-domain scan on the Internet Archive.
"""
import argparse
import json
from pathlib import Path
import re
from urllib.parse import unquote, urljoin

from bs4 import BeautifulSoup

from collect_wren import write_json
from wren_records import Record, Tables, make_id
from wren_sources import fetch_source

NOT_REBUILT_URL = "https://en.wikipedia.org/wiki/List_of_churches_destroyed_in_the_Great_Fire_of_London_and_not_rebuilt"
POPULATION_URL = "https://en.wikipedia.org/wiki/City_of_London"
NO_CENSUS_YEARS = {1941: "No UK census was held in 1941 (wartime); this value is not a census count."}
RELATED_SITES = [{
    "name": "The Monument to the Great Fire of London",
    "url": "https://en.wikipedia.org/wiki/Monument_to_the_Great_Fire_of_London",
    "keywords": ("Wren", "St Margaret, New Fish Street", "Constructed between"),
    "on_site_of_parish": "St Margaret, New Fish Street",
    "caveat": "Design developed by Robert Hooke; source says the extent of Wren's role cannot be known. Not a church.",
}]


def parse_related_site(html: str, site: Record, source_id: str, parishes: list[Record]) -> Tables:
    soup = BeautifulSoup(html, "html.parser")
    site_id = make_id("site", site["url"])
    geo = soup.select_one(".geo")
    coordinates = [float(value) for value in re.findall(r"-?\d+\.\d+", geo.get_text())[:2]] if geo else []
    claims = []
    for index, paragraph in enumerate(soup.select("#mw-content-text p"), start=1):
        text = paragraph.get_text(" ", strip=True)
        if any(keyword in text for keyword in site["keywords"]):
            claims.append({"claim_id": make_id("claim", f"{source_id}:{site_id}:p[{index}]"), "subject_id": site_id,
                           "source_id": source_id, "field": "related_site_passage", "locator": f"p[{index}]",
                           "value": {"text": text}, "review_status": "extracted"})
    parish = next((row for row in parishes if row["name"] == site.get("on_site_of_parish")), None)
    row = {"site_id": site_id, "name": site["name"], "article_url": site["url"], "role": "related_stop",
           "latitude": coordinates[0] if len(coordinates) == 2 else None,
           "longitude": coordinates[1] if len(coordinates) == 2 else None,
           "on_site_of_parish_id": parish["parish_id"] if parish else None, "evidence_tier": "reported",
           "caveat": site["caveat"], "claim_ids": [claim["claim_id"] for claim in claims]}
    return {"related_sites": [row], "claims": claims}


def parse_population(html: str, source_id: str) -> list[Record]:
    soup = BeautifulSoup(html, "html.parser")
    for table in soup.find_all("table"):
        header = [cell.get_text(" ", strip=True) for cell in table.find_all("th")[:3]]
        if header[:2] != ["Year", "Pop."]:
            continue
        rows = []
        for index, row in enumerate(table.find_all("tr")[1:], start=1):
            cells = [cell.get_text(" ", strip=True) for cell in row.find_all(["th", "td"])]
            year = re.match(r"(\d{4})", cells[0]) if cells else None
            count = re.fullmatch(r"[\d,]+", cells[1]) if len(cells) > 1 else None
            if not year or not count:
                continue
            label = cells[0]
            kind = "estimate" if "estimate" in label.lower() else "census"
            caveat = NO_CENSUS_YEARS.get(int(year[1]))
            rows.append({"year": int(year[1]), "population": int(cells[1].replace(",", "")),
                         "count_type": "not_census" if caveat else kind, "caveat": caveat,
                         "source_id": source_id, "locator": f"population table, row {index}"})
        return rows
    return []


def canonical_url(url: str) -> str:
    return unquote(url.split("#")[0]).replace(" ", "_")


def clean(text: str) -> str:
    return re.sub(r"\s*\[\s*\d+\s*\]|\s*\(ibid\)", "", text).strip()


def parse_not_rebuilt(html: str, base_url: str = NOT_REBUILT_URL) -> list[Record]:
    soup = BeautifulSoup(html, "html.parser")
    table = soup.find("table", class_="wikitable")
    rows = []
    for index, row in enumerate(table.find_all("tr")[1:] if table else [], start=1):
        cells = row.find_all(["td", "th"])
        if len(cells) < 3:
            continue
        name_link = cells[0].find("a", href=re.compile(r"^(/wiki/|https?://)(?!.*redlink=1)"))
        target_link = cells[2].find("a", href=re.compile(r"^(/wiki/|https?://)(?!.*redlink=1)"))
        rows.append({
            "name": clean(cells[0].get_text(" ", strip=True)),
            "location": clean(cells[1].get_text(" ", strip=True)),
            "united_with": clean(cells[2].get_text(" ", strip=True)),
            "article_url": canonical_url(urljoin(base_url, name_link["href"])) if name_link else None,
            "united_with_url": canonical_url(urljoin(base_url, target_link["href"])) if target_link else None,
            "locator": f"table 1, row {index}",
        })
    return rows


def name_key(name: str) -> str:
    text = re.sub(r"\b(church of|st\.?|saint|the|london)\b", " ", name.lower())
    return re.sub(r"[^a-z]+", "", text)


def link_parishes(rows: list[Record], churches: list[Record], source: Record,
                  overrides: dict[str, Record]) -> tuple[Tables, list[Record]]:
    by_url = {canonical_url(church.get("article_url") or ""): church["church_id"] for church in churches}
    by_name = {name_key(church["name"]): church["church_id"] for church in churches}
    tables: Tables = {"sources": [source], "parishes": [], "claims": [], "events": []}
    unmatched = []
    for row in rows:
        parish_id = make_id("parish", row["article_url"] or row["name"])
        override = overrides.get(row["united_with"])
        church_id = (by_url.get(row["united_with_url"] or "") or by_name.get(name_key(row["united_with"]))
                     or (override or {}).get("church_id"))
        claim = {"claim_id": make_id("claim", f"{source['source_id']}:{parish_id}:union"), "subject_id": parish_id,
                 "source_id": source["source_id"], "field": "parish_union", "locator": row["locator"],
                 "value": {"united_with": row["united_with"], "united_with_url": row["united_with_url"],
                           "location": row["location"]},
                 "review_status": "extracted"}
        tables["parishes"].append({"parish_id": parish_id, "name": row["name"], "article_url": row["article_url"],
                                   "status": "destroyed_1666_not_rebuilt", "united_church_id": church_id,
                                   "match_method": ("article_url" if by_url.get(row["united_with_url"] or "")
                                                    else "name" if by_name.get(name_key(row["united_with"]))
                                                    else "review_override" if church_id else None),
                                   "claim_ids": [claim["claim_id"]]})
        tables["claims"].append(claim)
        if not church_id:
            unmatched.append(row)
            continue
        tables["events"].append({"event_id": make_id("event", f"union:{parish_id}"), "church_id": church_id,
                                 "parish_id": parish_id, "kind": "parish_merger", "phase": "parish",
                                 "earliest_year": None, "latest_year": None, "date_role": "reported_without_year",
                                 "claim_ids": [claim["claim_id"]], "evidence_tier": "reported"})
    return tables, unmatched


def flat(text: str) -> str:
    return " ".join(text.split())


def parentalia_claims(review: Record, ocr_text: str, source_id: str, church_ids: set[str]) -> Tables:
    corpus = flat(ocr_text)
    if flat(review["heading_quote"]) not in corpus:
        raise ValueError("Parentalia heading quote not found in cached text")
    claims = []
    for entry in review["entries"]:
        if entry.get("quote") and flat(entry["quote"]) not in corpus:
            raise ValueError(f"Parentalia quote not found: {entry['quote']}")
        if entry["church_id"] is None:
            continue
        if entry["church_id"] not in church_ids:
            raise ValueError(f"Unknown church {entry['church_id']}")
        claims.append({"claim_id": make_id("claim", f"{source_id}:{entry['church_id']}:parentalia"),
                       "subject_id": entry["church_id"], "source_id": source_id, "field": "parentalia_entry",
                       "locator": f"Section IX, entry {entry['number']}",
                       "value": {key: entry.get(key) for key in ("number", "name", "year", "quote", "year_note")},
                       "review_status": "verified", "reviewed_at": review["reviewed_at"],
                       "review_rationale": "Entry and quoted wording checked against cached OCR text."})
    return {"claims": claims}


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect context tables for the Wren church study")
    parser.add_argument("--data", type=Path, default=Path("data/london_wren_churches"))
    parser.add_argument("--review", type=Path, default=Path("london-wren-churches/review"))
    args = parser.parse_args()
    cache = args.data / "cache"
    raw = json.loads((args.data / "tables_raw.json").read_text())
    source = fetch_source(NOT_REBUILT_URL, cache)
    if source["fetch_status"] != "ok":
        raise SystemExit(f"Could not fetch {NOT_REBUILT_URL}")
    rows = parse_not_rebuilt((cache / source["document_path"]).read_text())
    overrides_path = args.review / "parish_overrides.json"
    overrides = {row["united_with"]: row for row in json.loads(overrides_path.read_text())} if overrides_path.exists() else {}
    for row in overrides.values():
        if not row.get("rationale") or not row.get("reviewed_at"):
            raise SystemExit("Parish override requires rationale and reviewed_at")
    tables, unmatched = link_parishes(rows, raw["churches"], source, overrides)
    parentalia_path = args.review / "parentalia.json"
    if parentalia_path.exists():
        parentalia = json.loads(parentalia_path.read_text())
        parentalia_source = fetch_source(parentalia["source_url"], cache)
        if parentalia_source["fetch_status"] == "ok":
            tables["sources"].append(parentalia_source | {"publisher": "Parentalia (1750), Internet Archive OCR",
                                                          "licence": "Public domain text"})
            tables["claims"] += parentalia_claims(
                parentalia, (cache / parentalia_source["document_path"]).read_text(errors="replace"),
                parentalia_source["source_id"], {church["church_id"] for church in raw["churches"]})["claims"]
    population_source = fetch_source(POPULATION_URL, cache)
    if population_source["fetch_status"] == "ok":
        tables["sources"].append(population_source)
        tables["population"] = parse_population((cache / population_source["document_path"]).read_text(),
                                                 population_source["source_id"])
    tables["related_sites"] = []
    for site in RELATED_SITES:
        site_source = fetch_source(site["url"], cache)
        if site_source["fetch_status"] != "ok":
            continue
        tables["sources"].append(site_source)
        parsed = parse_related_site((cache / site_source["document_path"]).read_text(), site,
                                    site_source["source_id"], tables["parishes"])
        tables["related_sites"] += parsed["related_sites"]
        tables["claims"] += parsed["claims"]
    write_json(args.data / "context_tables.json", tables)
    print(json.dumps({"parishes": len(tables["parishes"]), "unions_linked": len(tables["events"]),
                      "population_rows": len(tables.get("population", [])),
                      "unmatched": [row["united_with"] for row in unmatched]}, indent=2))


if __name__ == "__main__":
    main()
