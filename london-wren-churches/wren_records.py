from collections import defaultdict
from copy import deepcopy
from hashlib import sha256
import json
import math
from typing import Any

type Record = dict[str, Any]
type Tables = dict[str, list[Record]]

ID_FIELDS = {
    "churches": "church_id", "places": "place_id", "events": "event_id",
    "sources": "source_id", "claims": "claim_id", "connections": "connection_id",
    "visits": "visit_id", "walks": "walk_id", "parishes": "parish_id", "related_sites": "site_id",
    "visitor_listings": "listing_id",
}
ENUMS = {
    "cohort": {"parish_replacement", "parish_repair", "parish_nonfire_rebuilding", "cathedral", "refurbishment", "outside_fire_area", "unresolved", "excluded"},
    "review_status": {"extracted", "verified", "disputed", "rejected"},
    "role": {"historical_site", "current_site", "visitor_entrance", "relocated_component", "related_stop"},
    "access_type": {"interior", "exterior", "garden", "tower", "unknown"},
    "kind": {"construction", "damage", "destruction", "restoration", "rebuilding", "alteration",
             "partial_demolition", "demolition", "parish_merger", "relocation"},
}


def make_id(namespace: str, value: str) -> str:
    encoded = json.dumps([namespace, value], ensure_ascii=True).encode()
    return f"{namespace}_{sha256(encoded).hexdigest()[:20]}"


def validate_tables(tables: Tables) -> list[str]:
    errors = []
    identifiers = {}
    for table, key in ID_FIELDS.items():
        seen = set()
        for row in tables.get(table, []):
            identifier = row.get(key)
            if not isinstance(identifier, str) or not identifier:
                errors.append(f"{table}: missing {key}")
            elif identifier in seen:
                errors.append(f"{table}: duplicate {key} {identifier}")
            else:
                seen.add(identifier)
        identifiers[table] = seen
    subjects = set().union(*(identifiers[table] for table in ID_FIELDS if table != "sources"))
    references = {"church_id": identifiers["churches"], "source_id": identifiers["sources"],
                  "place_id": identifiers["places"], "subject_id": subjects,
                  "parish_id": identifiers["parishes"], "on_site_of_parish_id": identifiers["parishes"],
                  "united_church_id": identifiers["churches"],
                  "from_id": subjects, "to_id": subjects}
    for table, rows in tables.items():
        for row in rows:
            identifier = row.get(ID_FIELDS.get(table, ""), "?")
            label = f"{table}/{identifier}"
            for field, allowed in ENUMS.items():
                if field in row and row[field] not in allowed:
                    errors.append(f"{label}: invalid {field}")
            for field, allowed in references.items():
                if field in row and field != ID_FIELDS.get(table) and row[field] is not None:
                    if row[field] not in allowed:
                        errors.append(f"{label}: dangling {field} {row[field]}")
            for field in ("claim_ids", "attribution_claim_ids", "identity_claim_ids"):
                for claim_id in row.get(field, []):
                    if claim_id not in identifiers["claims"]:
                        errors.append(f"{label}: dangling {field} {claim_id}")
            for field, limit in (("latitude", 90), ("longitude", 180)):
                value = row.get(field)
                if value is not None and (isinstance(value, bool) or not isinstance(value, (int, float))
                                          or not math.isfinite(value) or not -limit <= value <= limit):
                    errors.append(f"{label}: invalid {field}")
            earliest, latest = row.get("earliest_year"), row.get("latest_year")
            for value in (earliest, latest):
                if value is not None and (isinstance(value, bool) or not isinstance(value, int)):
                    errors.append(f"{label}: invalid date range")
            if isinstance(earliest, int) and isinstance(latest, int) and earliest > latest:
                errors.append(f"{label}: reversed date range")
            if table == "claims":
                for field in ("subject_id", "source_id", "field", "locator", "review_status"):
                    if not row.get(field):
                        errors.append(f"{label}: missing {field}")
    return errors


def resolve_claims(claims: list[Record], decisions: list[Record]) -> list[Record]:
    resolved = deepcopy(claims)
    indexed = {claim["claim_id"]: claim for claim in resolved}
    grouped = defaultdict(list)
    for claim in resolved:
        grouped[(claim["subject_id"], claim["field"])].append(claim)
    for (_, field), group in grouped.items():
        if field.endswith("_passage") or field in {"seed_section", "seed_cells"}:
            continue
        values = {json.dumps(claim["value"], sort_keys=True) for claim in group}
        if len(values) > 1:
            for claim in group:
                if claim["review_status"] == "extracted":
                    claim["review_status"] = "disputed"
    decided = set()
    for decision in decisions:
        if not decision.get("rationale", "").strip() or not decision.get("reviewed_at"):
            raise ValueError("Review requires rationale and reviewed_at")
        group_key = (decision["subject_id"], decision["field"])
        if group_key in decided:
            raise ValueError("Duplicate review decision for subject and field")
        decided.add(group_key)
        selected = decision.get("selected_claim_ids", [])
        rejected = decision.get("rejected_claim_ids", [])
        if set(selected) & set(rejected):
            raise ValueError("A claim cannot be selected and rejected")
        for claim_id in selected + rejected:
            claim = indexed.get(claim_id)
            if claim is None or (claim["subject_id"], claim["field"]) != group_key:
                raise ValueError("Review claim ownership does not match subject and field")
            claim["review_status"] = "verified" if claim_id in selected else "rejected"
            claim["review_rationale"] = decision["rationale"]
            claim["reviewed_at"] = decision["reviewed_at"]
    return resolved