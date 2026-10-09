import argparse
from collections import Counter, defaultdict
from copy import deepcopy
import json
from pathlib import Path

from collect_wren import write_json
from tiers_wren import choose_construction, derive_seed_events, listing_agreement
from wren_records import Record, Tables, make_id, resolve_claims, validate_tables

COVERAGE_FIELDS = {
    "construction_dates": {"seed_date_range", "construction_range"},
    "completion": {"completion"},
    "coordinates": {"seed_coordinates", "article_coordinates"},
    "attribution": {"infobox.architect", "attribution"},
    "cost": {"construction_cost", "infobox.construction_cost"},
    "loss_dates": {"loss_date", "infobox.demolished", "infobox.destroyed"},
    "current_fabric": {"current_fabric"},
    "visitor_hours": {"visitor_hours"},
    "published_visitor_listing": {"visitor_listing"},
    "accessibility": {"accessibility"},
}


def load_review(path: Path, default: object) -> object:
    return json.loads(path.read_text()) if path.exists() else default


def apply_date_reviews(tables: Tables, review: Record) -> None:
    reviewed_at = review.get("reviewed_at")
    churches = {row["church_id"] for row in tables["churches"]}
    claims = {row["claim_id"]: row for row in tables["claims"]}
    for entry in review.get("reviews", []):
        church_id, outcome = entry["church_id"], entry["outcome"]
        if church_id not in churches or not entry.get("rationale") or not reviewed_at:
            raise ValueError(f"Invalid date review for {church_id}")
        evidence = [claims.get(identifier) for identifier in entry.get("evidence_claim_ids", [])]
        if not evidence or any(claim is None or claim["subject_id"] != church_id for claim in evidence):
            raise ValueError(f"Date review evidence must belong to {church_id}")
        if outcome == "unresolved":
            continue
        field = "construction_milestone" if outcome == "verified_milestone" else "construction_range"
        claim = {"claim_id": make_id("claim", f"date_review:{church_id}:{outcome}"), "subject_id": church_id,
                 "field": field, "value": entry["value"], "phase": entry.get("phase", "unspecified"),
                 "source_id": evidence[0]["source_id"],
                 "locator": "evidence " + ", ".join(entry["evidence_claim_ids"]),
                 "review_status": "disputed" if outcome == "conflict" else "verified",
                 "review_rationale": entry["rationale"], "reviewed_at": reviewed_at, "caveat": entry.get("caveat")}
        tables["claims"].append(claim)
        if outcome == "conflict":
            continue
        earliest, latest = entry["value"]
        tables.setdefault("events", []).append({
            "event_id": make_id("event", f"date_review:{church_id}:{outcome}"), "church_id": church_id,
            "kind": "construction", "phase": claim["phase"], "earliest_year": earliest, "latest_year": latest,
            "claim_ids": [claim["claim_id"]], "date_basis": entry["rationale"],
            "date_role": "construction_interval" if outcome == "verified_interval" else entry["date_role"]})


def apply_loss_reasons(tables: Tables, review: Record) -> None:
    reviewed_at = review.get("reviewed_at")
    claims = {row["claim_id"]: row for row in tables["claims"]}
    for entry in review.get("reasons", []):
        church_id = entry["church_id"]
        evidence = [claims.get(identifier) for identifier in entry.get("evidence_claim_ids", [])]
        if not reviewed_at or not entry.get("rationale") or not evidence or any(
                claim is None or claim["subject_id"] != church_id for claim in evidence):
            raise ValueError(f"Invalid loss reason review for {church_id}")
        matched = [event for event in tables.get("events", [])
                   if event["church_id"] == church_id and event["kind"] in entry["kinds"]]
        if not matched:
            raise ValueError(f"No loss event to explain for {church_id}")
        for event in matched:
            event.update(mechanism=entry["mechanism"], reason_claim_ids=entry["evidence_claim_ids"],
                         reason_rationale=entry["rationale"], reason_reviewed_at=reviewed_at)


def apply_costs(tables: Tables, review: Record) -> None:
    claims = {row["claim_id"]: row for row in tables["claims"]}
    for entry in review.get("costs", []):
        evidence = claims.get(entry["evidence_claim_id"])
        if evidence is None or evidence["subject_id"] != entry["church_id"] or not review.get("reviewed_at"):
            raise ValueError(f"Invalid cost review for {entry['church_id']}")
        text = evidence["value"]["text"]
        if f"{entry['pounds']:,}" not in text and str(entry["pounds"]) not in text:
            raise ValueError(f"Cost £{entry['pounds']} not found in {entry['evidence_claim_id']}")
        shillings, pence = entry.get("shillings", 0), entry.get("pence", 0)
        tables["claims"].append({
            "claim_id": make_id("claim", f"cost:{entry['church_id']}:{entry['evidence_claim_id']}"),
            "subject_id": entry["church_id"], "field": "construction_cost", "source_id": evidence["source_id"],
            "locator": f"evidence {entry['evidence_claim_id']}", "review_status": "verified",
            "value": {"pounds": entry["pounds"], "shillings": shillings, "pence": pence,
                      "decimal_pounds": round(entry["pounds"] + shillings / 20 + pence / 240, 2),
                      "scope": entry["scope"], "note": entry.get("note")},
            "review_rationale": "Amount and scope read from the cited passage; nominal 17th-century pounds.",
            "reviewed_at": review["reviewed_at"]})


def apply_review(tables: Tables, review_dir: Path) -> Tables:
    reviewed = deepcopy(tables)
    identities = load_review(review_dir / "identities.json", [])
    indexed = {church["church_id"]: church for church in reviewed["churches"]}
    evidence = {claim["claim_id"]: claim for claim in reviewed["claims"]}
    remapping = {}
    for decision in identities:
        candidate = decision["candidate_id"]
        if candidate not in indexed:
            raise ValueError(f"Unknown identity candidate {candidate}")
        if not decision.get("rationale") or not decision.get("reviewed_at"):
            raise ValueError("Identity decision requires rationale and reviewed_at")
        for claim_id in decision.get("evidence_claim_ids", []):
            if claim_id not in evidence or evidence[claim_id]["subject_id"] != candidate:
                raise ValueError(f"Invalid identity evidence {claim_id} for {candidate}")
        remapping[candidate] = decision["church_id"]
        indexed[candidate].update(cohort=decision["cohort"], identity_rationale=decision["rationale"],
                                  identity_reviewed_at=decision["reviewed_at"])
        indexed[candidate]["identity_claim_ids"] = decision.get("evidence_claim_ids", [])
        indexed[candidate]["wren_work"] = decision.get("wren_work", "not_yet_scoped")
    for rows in reviewed.values():
        for row in rows:
            for field in ("church_id", "subject_id", "from_id", "to_id", "united_church_id"):
                if row.get(field) in remapping:
                    row[field] = remapping[row[field]]
    merged = {}
    for church in reviewed["churches"]:
        identifier = church["church_id"]
        if identifier in merged:
            retained = merged[identifier]
            retained["aliases"] = sorted(set(retained.get("aliases", []) + church.get("aliases", []) + [church["name"]]) - {retained["name"]})
            retained["seed_ids"] = sorted(set(retained.get("seed_ids", []) + church.get("seed_ids", [])))
        else:
            merged[identifier] = church
    reviewed["churches"] = list(merged.values())
    interpreted = load_review(review_dir / "interpretations.json", {})
    for table, rows in interpreted.items():
        reviewed.setdefault(table, []).extend(rows)
    decisions = load_review(review_dir / "claims.json", [])
    reviewed["claims"] = resolve_claims(reviewed["claims"], decisions)
    apply_date_reviews(reviewed, load_review(review_dir / "date_reviews.json", {}))
    apply_costs(reviewed, load_review(review_dir / "costs.json", {}))
    reviewed["visits"] = load_review(review_dir / "visits.json", reviewed.get("visits", []))
    seed_events, _ = derive_seed_events(reviewed)
    reviewed["events"] = reviewed.get("events", []) + seed_events
    apply_loss_reasons(reviewed, load_review(review_dir / "loss_reasons.json", {}))
    errors = validate_tables(reviewed)
    if errors:
        raise ValueError("\n".join(errors))
    return reviewed


def coverage_report(tables: Tables) -> Record:
    church_ids = {church["church_id"] for church in tables["churches"]}
    fields = {}
    for label, candidate_fields in COVERAGE_FIELDS.items():
        statuses = defaultdict(set)
        for claim in tables.get("claims", []):
            if claim["subject_id"] in church_ids and claim["field"] in candidate_fields and claim["value"] is not None:
                statuses[claim["subject_id"]].add(claim["review_status"])
        counts = {"verified": 0, "extracted": 0, "disputed": 0, "rejected": 0, "missing": 0}
        for church_id in church_ids:
            available = statuses[church_id]
            selected = next((status for status in ("disputed", "verified", "extracted", "rejected") if status in available), "missing")
            counts[selected] += 1
        fields[label] = counts
    failed = [source for source in tables.get("sources", []) if source.get("fetch_status") != "ok"]
    return {"churches": len(church_ids), "cohorts": dict(Counter(church["cohort"] for church in tables["churches"])),
            "sources": len(tables.get("sources", [])), "failed_sources": len(failed),
            "claim_statuses": dict(Counter(claim["review_status"] for claim in tables.get("claims", []))),
            "fields": fields, "events": len(tables.get("events", [])), "visits": len(tables.get("visits", [])),
            "limitations": ["Cohort unresolved until reconciliation is complete.",
                            "Extracted statements are not independently verified facts.",
                            "No live opening, step-free access or walking-time claims."]}


def gap_report(tables: Tables) -> Record:
    churches = {row["church_id"]: row for row in tables["churches"]}
    claims = {row["claim_id"]: row for row in tables["claims"]}
    fields = {}
    for label, candidate_fields in COVERAGE_FIELDS.items():
        verified = {claim["subject_id"] for claim in claims.values()
                    if claim["field"] in candidate_fields and claim.get("value") is not None
                    and claim["review_status"] == "verified" and claim["subject_id"] in churches}
        fields[label] = {"verified_churches": len(verified),
                         "needs_review_ids": sorted(set(churches) - verified)}
    dated_churches = set()
    for event in tables.get("events", []):
        identifiers = event.get("claim_ids", [])
        if identifiers and all(identifier in claims and claims[identifier]["review_status"] == "verified"
                               and claims[identifier]["subject_id"] == event["church_id"] for identifier in identifiers):
            dated_churches.add(event["church_id"])
    return {"candidate_count": len(churches), "fields": fields,
            "verified_event_churches": len(dated_churches),
            "no_verified_event_ids": sorted(set(churches) - dated_churches),
            "unresolved_cohort_ids": sorted(identifier for identifier, church in churches.items() if church["cohort"] == "unresolved"),
            "failed_source_urls": sorted(source["url"] for source in tables.get("sources", []) if source.get("fetch_status") != "ok"),
            "limitations": ["Missing structured values may already exist in unreviewed prose; not necessarily missing from source pages.",
                            "All-candidate denominators include cathedral, repairs and out-of-area sites; not a representative parish sample.",
                            "Verified reporting windows and published visitor statements do not imply adjudicated exact dates or live availability.",
                            "Construction dates include reported ranges; phase-specific body intervals require separate event review."]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Apply explicit Wren evidence review decisions")
    parser.add_argument("--data", type=Path, default=Path("data/london_wren_churches"))
    parser.add_argument("--review", type=Path, default=Path("london-wren-churches/review"))
    args = parser.parse_args()
    tables = json.loads((args.data / "tables_raw.json").read_text())
    context_path = args.data / "context_tables.json"
    for extra_path in (context_path, args.data / "visitor_tables.json"):
        if not extra_path.exists():
            continue
        for table, rows in json.loads(extra_path.read_text()).items():
            known = {row.get("source_id") for row in tables.get(table, [])} if table == "sources" else set()
            tables.setdefault(table, []).extend(row for row in rows if table != "sources" or row["source_id"] not in known)
    reviewed = apply_review(tables, args.review)
    report = coverage_report(reviewed)
    write_json(args.data / "tables_reviewed.json", reviewed)
    write_json(args.data / "coverage.json", report)
    write_json(args.data / "gaps.json", gap_report(reviewed))
    write_json(args.data / "construction_tiers.json", choose_construction(reviewed))
    write_json(args.data / "listing_agreement.json", listing_agreement(reviewed))
    write_json(args.data / "seed_unparsed.json", derive_seed_events(reviewed)[1])
    seed_rows = json.loads((args.data / "seed_rows.json").read_text())
    reconciliation = {"seed_rows": len(seed_rows), "reviewed_entities": len(reviewed["churches"]),
                      "accounted_seed_ids": sorted(seed_id for church in reviewed["churches"] for seed_id in church.get("seed_ids", [])),
                      "unresolved": [{"church_id": church["church_id"], "name": church["name"]} for church in reviewed["churches"] if church["cohort"] == "unresolved"],
                      "source_denominator": "Introduction says 51 parish replacements plus cathedral; main fate tables have 51 rows including cathedral."}
    catalogue = {claim["subject_id"] for claim in reviewed["claims"] if claim["field"] == "parentalia_entry"}
    if catalogue:
        cohorts = {church["church_id"]: church["cohort"] for church in reviewed["churches"]}
        in_fire_area = {identifier for identifier in catalogue
                        if cohorts.get(identifier) not in {"outside_fire_area", "parish_nonfire_rebuilding"}}
        reconciliation["parentalia"] = {
            "register_entries_in_catalogue": len(catalogue),
            "by_cohort": dict(sorted(Counter(cohorts[identifier] for identifier in catalogue).items())),
            "register_entries_not_in_catalogue": sorted(church["name"] for church in reviewed["churches"]
                                                        if church["church_id"] not in catalogue),
            "fire_area_entries_in_register": len(in_fire_area),
            "note": "Parentalia lists 54 entries; two (St Mary Woolnoth, St Sepulchre) are not register candidates. "
                    "Fire-area register entries plus those two give the catalogue's 51 parochial churches."}
    if set(reconciliation["accounted_seed_ids"]) != {row["seed_id"] for row in seed_rows}:
        raise SystemExit("Reconciliation does not account for every seed row")
    write_json(args.data / "reconciliation.json", reconciliation)
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()