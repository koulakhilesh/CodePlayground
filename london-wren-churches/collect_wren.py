"""Collect the Wren register: the seed list, each church's article, and the references they cite.

Sources: Wikipedia, List of Christopher Wren churches in London and linked church articles
(CC BY-SA 4.0); Historic England National Heritage List entries cited by those articles (OGL v3.0).
Full source list and licences: README.md, "Data sources".
"""
import argparse
from collections import Counter
import json
from pathlib import Path
import re
import time
from urllib.parse import urldefrag, urljoin, urlparse

from bs4 import BeautifulSoup

from wren_records import Record, Tables, make_id, validate_tables
from wren_sources import fetch_source

SEED_URL = "https://en.wikipedia.org/wiki/List_of_Christopher_Wren_churches_in_London"


def parse_year_range(text: str) -> list[int] | None:
    cleaned = re.sub(r"\[\d+\]", "", text).strip()
    match = re.fullmatch(r"(\d{4})(?:\s*[-\u2013\u2014]\s*(\d{2}|\d{4}))?", cleaned)
    if not match:
        return None
    start = int(match.group(1))
    end_text = match.group(2)
    end = int(end_text) if end_text else start
    if end_text and len(end_text) == 2:
        end += start // 100 * 100
        if end < start:
            end += 100
    return [start, end] if end >= start else None


def parse_coordinates(text: str) -> list[float] | None:
    decimal = re.fullmatch(r"\s*(-?\d+(?:\.\d+)?)\s*;\s*(-?\d+(?:\.\d+)?)\s*", text)
    if decimal:
        values = [float(decimal.group(1)), float(decimal.group(2))]
    else:
        matches = re.findall(r"(\d+(?:\.\d+)?)[\u00b0]\s*(\d+(?:\.\d+)?)?[\u2032']?\s*(\d+(?:\.\d+)?)?[\u2033\"]?\s*([NSEW])", text)
        if len(matches) != 2 or matches[0][3] not in "NS" or matches[1][3] not in "EW":
            return None
        values = []
        for degrees, minutes, seconds, direction in matches:
            if float(minutes or 0) >= 60 or float(seconds or 0) >= 60:
                return None
            value = float(degrees) + float(minutes or 0) / 60 + float(seconds or 0) / 3600
            values.append(-value if direction in "SW" else value)
    return values if abs(values[0]) <= 90 and abs(values[1]) <= 180 else None


def parse_seed(html: str, source_id: str, base_url: str) -> list[Record]:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#mw-content-text") or soup
    section = ""
    output = []
    table_index = 0
    for element in root.find_all(["h2", "h3", "table"]):
        if element.name in {"h2", "h3"}:
            section = element.get_text(" ", strip=True).replace("[ edit ]", "").replace("[edit]", "").strip()
            continue
        if "wikitable" not in element.get("class", []):
            continue
        table_index += 1
        rows = element.find_all("tr")
        if not rows:
            continue
        headers = [cell.get_text(" ", strip=True) for cell in rows[0].find_all(["th", "td"], recursive=False)]
        if "Name" not in headers:
            continue
        for row_index, row in enumerate(rows[1:], 1):
            cells = row.find_all(["td", "th"], recursive=False)
            if len(cells) != len(headers):
                raise ValueError(f"Malformed seed row at table {table_index}, row {row_index}")
            mapped = dict(zip(headers, cells, strict=True))
            name_cell = mapped["Name"]
            anchor = name_cell.find("a", href=re.compile(r"^(?:https?://en\.wikipedia\.org/wiki/|/wiki/|\./)(?!File:|Help:)"))
            raw = {header: cell.get_text(" ", strip=True) for header, cell in mapped.items()}
            locator = f"table[{table_index}]/row[{row_index}]"
            geo = mapped.get("Coordinates")
            geo_span = geo.select_one(".geo") if geo is not None else None
            coordinate_text = geo_span.get_text(" ", strip=True) if geo_span else raw.get("Coordinates", "")
            output.append({"seed_id": make_id("seed", source_id + ":" + locator),
                           "source_id": source_id, "locator": locator, "section": section,
                           "name": raw["Name"], "article_url": urljoin(base_url, anchor["href"]) if anchor else None,
                           "raw_cells": raw, "date_range": parse_year_range(raw.get("Date", "")),
                           "coordinates": parse_coordinates(coordinate_text)})
    if not output:
        raise ValueError("No seed rows found; source may be blocked or changed")
    return output


def seed_tables(rows: list[Record], source: Record) -> Tables:
    tables: Tables = {"churches": [], "sources": [source], "claims": [], "places": [], "events": []}
    churches = {}
    for row in rows:
        identity = row["article_url"] or row["seed_id"]
        church_id = make_id("church", identity)
        row["church_id"] = church_id
        if church_id not in churches:
            church = {"church_id": church_id, "name": row["name"], "aliases": [],
                      "article_url": row["article_url"], "cohort": "unresolved", "seed_ids": [],
                      "attribution_claim_ids": []}
            churches[church_id] = church
            tables["churches"].append(church)
        church = churches[church_id]
        church["seed_ids"].append(row["seed_id"])
        if row["name"] != church["name"] and row["name"] not in church["aliases"]:
            church["aliases"].append(row["name"])
        for field, value in (("seed_section", row["section"]), ("seed_date_range", row["date_range"]),
                             ("seed_cells", row["raw_cells"])):
            claim = {"claim_id": make_id("claim", row["seed_id"] + ":" + field),
                     "subject_id": church_id, "field": field, "value": value,
                     "source_id": source["source_id"], "locator": row["locator"], "review_status": "extracted"}
            tables["claims"].append(claim)
        if row["coordinates"] is not None:
            claim_id = make_id("claim", row["seed_id"] + ":coordinates")
            tables["claims"].append({"claim_id": claim_id, "subject_id": church_id,
                                     "field": "seed_coordinates", "value": row["coordinates"],
                                     "source_id": source["source_id"], "locator": row["locator"],
                                     "review_status": "extracted"})
            tables["places"].append({"place_id": make_id("place", row["seed_id"]),
                                     "church_id": church_id, "role": "historical_site",
                                     "latitude": row["coordinates"][0], "longitude": row["coordinates"][1],
                                     "precision": "source_reported_unverified", "claim_ids": [claim_id]})
    return tables


def write_json(path: Path, value: object) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(value, indent=2, ensure_ascii=True, sort_keys=True) + "\n")


def extract_article(html: str, church_id: str, source_id: str) -> Tables:
    soup = BeautifulSoup(html, "html.parser")
    root = soup.select_one("#mw-content-text") or soup
    tables: Tables = {"claims": [], "places": [], "events": [], "source_targets": []}

    def add_claim(field: str, value: object, locator: str) -> None:
        tables["claims"].append({"claim_id": make_id("claim", source_id + ":" + church_id + ":" + locator),
                                 "subject_id": church_id, "field": field, "value": value,
                                 "source_id": source_id, "locator": locator, "review_status": "extracted"})

    infobox = root.select_one("table.infobox")
    if infobox:
        for row_index, row in enumerate(infobox.find_all("tr"), 1):
            heading = row.find("th", recursive=False)
            value = row.find("td", recursive=False)
            if heading is not None and value is not None:
                key = re.sub(r"[^a-z0-9]+", "_", heading.get_text(" ", strip=True).lower()).strip("_")
                add_claim("infobox." + key, value.get_text(" ", strip=True), f"infobox/row[{row_index}]")
    geo = root.select_one(".geo")
    if geo:
        coordinates = parse_coordinates(geo.get_text(" ", strip=True))
        if coordinates is not None:
            add_claim("article_coordinates", coordinates, "span.geo[1]")
    section = "Introduction"
    paragraph_index = 0
    for element in root.find_all(["h2", "h3", "p"]):
        if element.name in {"h2", "h3"}:
            section = element.get_text(" ", strip=True).replace("[ edit ]", "").replace("[edit]", "").strip()
        elif element.find_parent("table") is None:
            paragraph_index += 1
            text = element.get_text(" ", strip=True)
            if text and section.lower() not in {"references", "notes", "external links", "see also"}:
                add_claim("history_passage", {"section": section, "text": text}, f"p[{paragraph_index}]")
    seen_urls = set()
    for link_index, anchor in enumerate(root.select("a.external[href]"), 1):
        url, _ = urldefrag(str(anchor["href"]))
        if url.startswith(("https://", "http://")) and url not in seen_urls:
            seen_urls.add(url)
            tables["source_targets"].append({"subject_id": church_id, "url": url,
                                             "label": anchor.get_text(" ", strip=True),
                                             "discovered_from": source_id,
                                             "locator": f"external-link[{link_index}]"})
    return tables


def collect_articles(output_dir: Path, *, refresh: bool = False) -> None:
    seed_source = fetch_source(SEED_URL, output_dir / "cache")
    if seed_source["fetch_status"] != "ok":
        raise SystemExit("Collect a successful seed before article collection")
    rows = json.loads((output_dir / "seed_rows.json").read_text())
    tables = seed_tables(rows, seed_source)
    targets = []
    failures = []
    for index, church in enumerate(tables["churches"], 1):
        url = church["article_url"]
        if not url:
            failures.append({"church_id": church["church_id"], "error": "No article link"})
            continue
        cache_path = output_dir / "cache" / f"{make_id('source', url)}.json"
        if refresh or not cache_path.exists():
            time.sleep(1.0)
        source = fetch_source(url, output_dir / "cache", refresh=refresh)
        tables["sources"].append(source)
        if source["fetch_status"] == "ok":
            html = (output_dir / "cache" / source["document_path"]).read_text(errors="replace")
            evidence = extract_article(html, church["church_id"], source["source_id"])
            tables["claims"].extend(evidence["claims"])
            targets.extend(evidence["source_targets"])
            if not evidence["claims"]:
                failures.append({"church_id": church["church_id"], "source_id": source["source_id"],
                                 "error": "No article evidence extracted"})
        else:
            failures.append({"church_id": church["church_id"], "source_id": source["source_id"],
                             "error": source["error"]})
        write_json(output_dir / "tables_raw.json", tables)
        write_json(output_dir / "discovered_sources.json", targets)
        write_json(output_dir / "collection_failures.json", failures)
        print(f"[{index}/{len(tables['churches'])}] {church['name']}: {source['fetch_status']}", flush=True)
    errors = validate_tables(tables)
    if errors:
        raise SystemExit("\n".join(errors))
    print(json.dumps({"article_sources": len(tables["sources"]) - 1,
                      "failures": len(failures), "claims": len(tables["claims"]),
                      "discovered_links": len(targets)}, indent=2))


def reference_targets(discovered: list[Record], explicit: list[Record]) -> list[Record]:
    targets = {}
    for link in discovered:
        parsed = urlparse(link["url"])
        if parsed.hostname == "historicengland.org.uk" and re.fullmatch(r"/listing/the-list/list-entry/\d+/?", parsed.path):
            url = "https://historicengland.org.uk" + parsed.path.rstrip("/")
            targets[(link["subject_id"], url)] = {**link, "url": url, "publisher": "Historic England",
                                                "intended_fields": ["construction", "attribution", "fabric"]}
    for target in explicit:
        targets[(target["subject_id"], target["url"])] = target
    return list(targets.values())


def extract_reference(html: str, church_id: str, source_id: str, *, relationship: str = "unreviewed_reference") -> Tables:
    soup = BeautifulSoup(html, "html.parser")
    visitor_source = relationship == "visitor_information"
    root = soup if visitor_source else (soup.find("main") or soup)
    section = "Introduction"
    claims = []
    paragraph_index = 0
    field = {"context_only": "context_passage", "visitor_information": "visitor_source_passage",
             "relocated_component": "relocation_passage"}.get(relationship, "official_entry_passage")
    elements = ["h1", "h2", "h3", "h4", "p", "dl"] + (["h5", "h6"] if visitor_source else [])
    for element in root.find_all(elements):
        if element.name.startswith("h") and element.name not in {"h5", "h6"}:
            section = element.get_text(" ", strip=True)
        else:
            paragraph_index += 1
            text = element.get_text(" ", strip=True)
            if text:
                locator = f"reference-block[{paragraph_index}]"
                claims.append({"claim_id": make_id("claim", source_id + ":" + church_id + ":" + locator),
                               "subject_id": church_id, "field": field,
                               "value": {"section": section, "text": text}, "source_id": source_id,
                               "locator": locator, "review_status": "extracted", "relationship": relationship})
    return {"claims": claims}


def collect_references(output_dir: Path, review_dir: Path, *, refresh: bool = False, retry_failed: bool = False) -> None:
    tables = json.loads((output_dir / "tables_raw.json").read_text())
    discovered = json.loads((output_dir / "discovered_sources.json").read_text())
    target_file = review_dir / "source_targets.json"
    explicit = json.loads(target_file.read_text()) if target_file.exists() else []
    targets = reference_targets(discovered, explicit)
    write_json(output_dir / "reference_targets.json", targets)
    sources = {source["source_id"]: source for source in tables["sources"]}
    claims = {claim["claim_id"]: claim for claim in tables["claims"]}
    reference_report = []
    for index, target in enumerate(targets, 1):
        url = target["url"]
        cache_path = output_dir / "cache" / f"{make_id('source', url)}.json"
        failed_cache = cache_path.exists() and json.loads(cache_path.read_text())["fetch_status"] != "ok"
        if refresh or not cache_path.exists() or (retry_failed and failed_cache):
            time.sleep(1.0)
        source = fetch_source(url, output_dir / "cache", refresh=refresh, retry_failed=retry_failed)
        sources[source["source_id"]] = source
        evidence_count = 0
        if source["fetch_status"] == "ok":
            html = (output_dir / "cache" / source["document_path"]).read_text(errors="replace")
            evidence = extract_reference(html, target["subject_id"], source["source_id"],
                                         relationship=target.get("relationship", "unreviewed_reference"))
            for claim in evidence["claims"]:
                claims[claim["claim_id"]] = claim
            evidence_count = len(evidence["claims"])
        reference_report.append({**target, "source_id": source["source_id"],
                                 "fetch_status": source["fetch_status"], "claims": evidence_count})
        tables["sources"] = list(sources.values())
        tables["claims"] = list(claims.values())
        write_json(output_dir / "tables_raw.json", tables)
        write_json(output_dir / "reference_collection.json", reference_report)
        print(f"[{index}/{len(targets)}] {url}: {source['fetch_status']}, {evidence_count} passages", flush=True)
    print(json.dumps({"reference_targets": len(targets), "fetched": sum(row["fetch_status"] == "ok" for row in reference_report),
                      "churches_with_references": len({row["subject_id"] for row in reference_report if row["fetch_status"] == "ok"})}, indent=2))


def inspect_evidence(output_dir: Path, names: list[str]) -> None:
    tables = json.loads((output_dir / "tables_raw.json").read_text())
    for church in tables["churches"]:
        if names and not any(name.casefold() in church["name"].casefold() for name in names):
            continue
        print(f"\n{church['name']} | {church['church_id']}")
        for claim in tables["claims"]:
            if claim["subject_id"] != church["church_id"]:
                continue
            value = claim["value"]
            text = value.get("text", "") if isinstance(value, dict) else str(value)
            if claim["field"] == "official_entry_passage" and value.get("section") != "Details":
                continue
            if claim["field"] == "history_passage" and not re.search(r"\b(?:16\d\d|17\d\d|18\d\d|19\d\d|Wren|Hooke|Hawksmoor)\b", text):
                continue
            if claim["field"] == "seed_cells":
                continue
            print(f"{claim['claim_id']} | {claim['source_id']} | {claim['locator']} | {claim['field']}: {text}")


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect source-labelled Wren church evidence")
    parser.add_argument("stage", choices=["seed", "articles", "references", "inspect"])
    parser.add_argument("--output", type=Path, default=Path("data/london_wren_churches"))
    parser.add_argument("--refresh", action="store_true")
    parser.add_argument("--retry-failed", action="store_true", help="Retry failed reference sources without refetching successful pages")
    parser.add_argument("--review", type=Path, default=Path("london-wren-churches/review"))
    parser.add_argument("--names", nargs="*", default=[])
    args = parser.parse_args()
    if args.stage == "references":
        collect_references(args.output, args.review, refresh=args.refresh, retry_failed=args.retry_failed)
        return
    if args.stage == "inspect":
        inspect_evidence(args.output, args.names)
        return
    if args.stage == "articles":
        collect_articles(args.output, refresh=args.refresh)
        return
    source = fetch_source(SEED_URL, args.output / "cache", refresh=args.refresh)
    if source["fetch_status"] != "ok":
        write_json(args.output / "collection_failures.json", [source])
        raise SystemExit(f"Seed fetch failed: {source['error']}; evidence recorded")
    html = (args.output / "cache" / source["document_path"]).read_text(errors="replace")
    rows = parse_seed(html, source["source_id"], SEED_URL)
    tables = seed_tables(rows, source)
    errors = validate_tables(tables)
    if errors:
        raise SystemExit("\n".join(errors))
    write_json(args.output / "seed_rows.json", rows)
    write_json(args.output / "tables_raw.json", tables)
    print(json.dumps({"seed_rows": len(rows), "unique_candidates": len(tables["churches"]),
                      "sections": dict(Counter(row["section"] for row in rows)),
                      "coordinates": sum(row["coordinates"] is not None for row in rows)}, indent=2))


if __name__ == "__main__":
    main()