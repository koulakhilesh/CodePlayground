"""Third-party published visitor listings (Friends of the City Churches) for the Wren study.

Statements are stored as published text with the date checked. They are not live availability,
and hours are not parsed into open/closed predictions. Source: fotcc.org.uk church pages
(copyright Friends of the City Churches; quote briefly with a link).
"""
import argparse
import html as html_lib
import json
from pathlib import Path
import re
import time

from bs4 import BeautifulSoup

from collect_wren import write_json
from context_wren import name_key
from wren_records import Record, Tables, make_id
from wren_sources import fetch_source

LISTING_URL = "https://www.fotcc.org.uk/wp-json/wp/v2/church?per_page=100&_fields=slug,link,title"
SCOPE_PATTERNS = [
    (r"tower and gardens? only", "tower_and_garden"), (r"gardens? and remains only", "garden_and_remains"),
    (r"tower only", "tower"), (r"gardens? only", "garden"),
]
STATUS_RULES = [
    (re.compile(r"\b(closed for|will be closed|closure|refurbish\w*|not open to the public|until further notice)\b", re.I), "closure_notice"),
    (re.compile(r"\bno regular opening\b", re.I), "no_regular_hours"),
    (re.compile(r"\bby (arrangement|appointment)\b", re.I), "by_arrangement"),
    (re.compile(r"\d"), "hours_published"),
]


def published_status(opening: str | None) -> str:
    if not opening:
        return "no_hours_listed"
    return next((status for pattern, status in STATUS_RULES if pattern.search(opening)), "text_only")


def listing_scope(title: str) -> tuple[str, str]:
    lowered = title.lower()
    for pattern, scope in SCOPE_PATTERNS:
        if re.search(pattern, lowered):
            return re.sub(r"\s*\(.*\)\s*$", "", title).strip(), scope
    return title.strip(), "interior"


def parse_listing_page(html: str) -> Record:
    soup = BeautifulSoup(html, "html.parser")
    items = {}
    for item in soup.select(".church-info-item"):
        title = item.select_one(".church-info-title")
        text = item.select_one(".church-info-text")
        if title and text:
            items[title.get_text(" ", strip=True)] = text.get_text(" ", strip=True)
    opening = items.get("Usual opening times")
    status = published_status(opening)
    return {"opening_text": opening, "location_text": items.get("Location"),
            "watchers_text": items.get("City church watchers present"),
            "published_status": status, "closure_notice": status == "closure_notice",
            "fee_mentioned": bool(opening and re.search(r"\b(fee|charged?|admission)\b", opening, re.I))}


def match_listing(name: str, churches: list[Record], overrides: dict[str, Record],
                  parishes: list[Record] | None = None) -> tuple[str | None, str | None]:
    if name in overrides:
        return overrides[name].get("church_id") or overrides[name].get("parish_id"), "review_override"
    key = name_key(name)
    for rows, identifier, method in ((churches, "church_id", "name"), (parishes or [], "parish_id", "parish_name")):
        exact = {row[identifier] for row in rows if name_key(row["name"]) == key}
        if len(exact) == 1:
            return exact.pop(), method
    return None, None


def build_listings(index: list[Record], pages: dict[str, tuple[Record, str]], churches: list[Record],
                   overrides: dict[str, Record], parishes: list[Record] | None = None) -> tuple[Tables, list[str]]:
    tables: Tables = {"visitor_listings": [], "claims": []}
    unmatched = []
    parish_ids = {row["parish_id"] for row in parishes or []}
    for entry in sorted(index, key=lambda row: row["link"]):
        title = html_lib.unescape(entry["title"]["rendered"])
        name, scope = listing_scope(title)
        subject_id, method = match_listing(name, churches, overrides, parishes)
        if not subject_id:
            unmatched.append(title)
            continue
        page = pages.get(entry["link"])
        if not page:
            continue
        source, html = page
        parsed = parse_listing_page(html)
        claim = {"claim_id": make_id("claim", f"{source['source_id']}:{subject_id}:visitor_listing"),
                 "subject_id": subject_id, "source_id": source["source_id"], "field": "visitor_listing",
                 "locator": "church-info-item blocks", "value": {"title": title, **parsed},
                 "review_status": "extracted"}
        tables["claims"].append(claim)
        is_parish = subject_id in parish_ids
        tables["visitor_listings"].append({
            "listing_id": make_id("listing", entry["link"]), "church_id": None if is_parish else subject_id,
            "parish_id": subject_id if is_parish else None, "title": title,
            "access_scope": scope, "url": entry["link"], "match_method": method, **parsed,
            "publisher": "Friends of the City Churches", "evidence_tier": "third_party_published",
            "checked_at": source["retrieved_at"][:10], "claim_ids": [claim["claim_id"]],
        })
    return tables, unmatched


def normalise(text: str) -> str:
    return " ".join(text.replace("\u2019", "'").replace("\u200b", "").split())


def official_listings(review: Record, tables: Tables) -> Tables:
    sources = {row["source_id"]: row for row in tables["sources"]}
    out: Tables = {"visitor_listings": [], "claims": []}
    for page in review.get("pages", []):
        passages = [claim for claim in tables["claims"]
                    if claim["field"] == "visitor_source_passage" and claim["subject_id"] == page["church_id"]
                    and sources.get(claim["source_id"], {}).get("url") == page["url"]]
        if not passages:
            raise ValueError(f"No cached visitor passages for {page['url']}")
        corpus = normalise(" ".join(claim["value"]["text"] for claim in passages))
        quotes = {key: page.get(key, []) for key in ("opening_quotes", "fee_quotes", "accessibility_quotes")}
        missing = [quote for values in quotes.values() for quote in values if normalise(quote) not in corpus]
        if missing:
            raise ValueError(f"Quotes not found in cached page {page['url']}: {missing}")
        source = sources[passages[0]["source_id"]]
        claim = {"claim_id": make_id("claim", f"{source['source_id']}:{page['church_id']}:official_visitor"),
                 "subject_id": page["church_id"], "source_id": source["source_id"], "field": "visitor_listing",
                 "locator": "quoted visitor_source_passage text", "value": quotes, "review_status": "verified",
                 "review_rationale": "Quotes matched against the cached official page.", "reviewed_at": review["reviewed_at"]}
        out["claims"].append(claim)
        out["visitor_listings"].append({
            "listing_id": make_id("listing", page["url"]), "church_id": page["church_id"], "parish_id": None,
            "title": page["publisher"], "access_scope": page["access_scope"], "url": page["url"],
            "match_method": "official_site", "opening_text": " ".join(quotes["opening_quotes"]),
            "fee_text": " ".join(quotes["fee_quotes"]) or None,
            "accessibility_text": " ".join(quotes["accessibility_quotes"]) or None,
            "location_text": None, "watchers_text": None, "published_status": page["published_status"],
            "closure_notice": False, "fee_mentioned": bool(quotes["fee_quotes"]), "notes": page.get("notes"),
            "publisher": page["publisher"], "evidence_tier": "official_published",
            "checked_at": source["retrieved_at"][:10], "claim_ids": [claim["claim_id"]]})
    return out


def access_claims(review: Record, cache: Path) -> Tables:
    out: Tables = {"claims": [], "sources": []}
    for statement in review.get("statements", []):
        source = fetch_source(statement["url"], cache)
        if source["fetch_status"] != "ok":
            raise ValueError(f"Access page not cached: {statement['url']}")
        text = normalise(BeautifulSoup((cache / source["document_path"]).read_text(errors="replace"), "html.parser").get_text(" "))
        missing = [quote for quote in statement["quotes"] if normalise(quote) not in text]
        if missing:
            raise ValueError(f"Access quotes not found on {statement['url']}: {missing}")
        out["sources"].append(source)
        out["claims"].append({
            "claim_id": make_id("claim", f"{source['source_id']}:{statement['church_id']}:accessibility"),
            "subject_id": statement["church_id"], "source_id": source["source_id"], "field": "accessibility",
            "locator": "quoted page text", "review_status": "verified", "reviewed_at": review["reviewed_at"],
            "value": {"step_free_main_space": statement["step_free_main_space"], "quotes": statement["quotes"],
                      "checked_at": source["retrieved_at"][:10]},
            "review_rationale": "Published access statement quoted from the official site; not a site survey."})
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description="Collect third-party published visitor listings")
    parser.add_argument("--data", type=Path, default=Path("data/london_wren_churches"))
    parser.add_argument("--review", type=Path, default=Path("london-wren-churches/review"))
    args = parser.parse_args()
    cache = args.data / "cache"
    raw = json.loads((args.data / "tables_raw.json").read_text())
    context_path = args.data / "context_tables.json"
    parishes = json.loads(context_path.read_text()).get("parishes", []) if context_path.exists() else []
    overrides_path = args.review / "visitor_overrides.json"
    overrides = {row["name"]: row for row in json.loads(overrides_path.read_text())} if overrides_path.exists() else {}
    for row in overrides.values():
        if not row.get("rationale") or not row.get("reviewed_at"):
            raise SystemExit("Visitor override requires rationale and reviewed_at")
    index_source = fetch_source(LISTING_URL, cache)
    if index_source["fetch_status"] != "ok":
        raise SystemExit("Could not fetch listing index")
    index = json.loads((cache / index_source["document_path"]).read_text())
    pages = {}
    sources = [index_source]
    for entry in index:
        name, _ = listing_scope(html_lib.unescape(entry["title"]["rendered"]))
        if not match_listing(name, raw["churches"], overrides, parishes)[0]:
            continue
        cache_file = cache / f"{make_id('source', entry['link'])}.json"
        if not cache_file.exists():
            time.sleep(1.0)
        source = fetch_source(entry["link"], cache)
        if source["fetch_status"] == "ok":
            sources.append(source)
            pages[entry["link"]] = (source, (cache / source["document_path"]).read_text(errors="replace"))
    tables, unmatched = build_listings(index, pages, raw["churches"], overrides, parishes)
    official_path = args.review / "official_visitor_pages.json"
    if official_path.exists():
        official = official_listings(json.loads(official_path.read_text()), raw)
        tables["visitor_listings"] += official["visitor_listings"]
        tables["claims"] += official["claims"]
    tables["sources"] = sources
    access_path = args.review / "access_statements.json"
    if access_path.exists():
        access = access_claims(json.loads(access_path.read_text()), cache)
        tables["claims"] += access["claims"]
        tables["sources"] += access["sources"]
    write_json(args.data / "visitor_tables.json", tables)
    print(json.dumps({"listings": len(tables["visitor_listings"]), "unmatched_titles": unmatched}, indent=2))


if __name__ == "__main__":
    main()
