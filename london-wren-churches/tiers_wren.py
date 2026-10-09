from collections import defaultdict
import json
import re

from wren_records import Record, Tables, make_id

YEAR_RANGE = r"(\d{4})(?:\s*[–-]\s*(\d{1,4}))?"
LISTING_RANGE = re.compile(r"\b(16[6-9]\d|17[0-2]\d)\s*(?:to|–|-)\s*(\d{1,4})\b")


def expand_range(start: str, end: str | None) -> list[int]:
    first = int(start)
    if not end:
        return [first, first]
    last = int(end)
    if len(end) < 4:
        scale = 10 ** len(end)
        last = first - first % scale + last
        if last < first:
            last += scale
    return [first, last]


def seed_claims(tables: Tables) -> dict[str, dict[str, Record]]:
    grouped: dict[str, dict[str, Record]] = defaultdict(dict)
    for claim in tables["claims"]:
        if claim["field"] in {"seed_section", "seed_cells", "seed_date_range"}:
            grouped[claim["subject_id"]].setdefault(claim["field"], claim)
    return grouped


def derive_seed_events(tables: Tables) -> tuple[list[Record], list[Record]]:
    events: list[Record] = []
    unparsed: list[Record] = []
    for church_id, claims in sorted(seed_claims(tables).items()):
        section = claims.get("seed_section", {}).get("value", "")
        cells = claims.get("seed_cells", {}).get("value", {}) or {}
        cell_claim = claims.get("seed_cells") or claims.get("seed_section")
        found: list[Record] = []

        def add(kind: str, phase: str, years: list[int | None], role: str, **extra: object) -> None:
            if any(row["kind"] == kind and row["phase"] == phase and [row["earliest_year"], row["latest_year"]] == years for row in found):
                return
            found.append({"kind": kind, "phase": phase, "earliest_year": years[0], "latest_year": years[1],
                          "date_role": role, **extra})

        date_claim = claims.get("seed_date_range")
        if date_claim and date_claim.get("value"):
            start, end = date_claim["value"]
            events.append({"event_id": make_id("event", f"seed:{church_id}:construction"), "church_id": church_id,
                           "kind": "construction", "phase": "seed_scope_unspecified", "earliest_year": start,
                           "latest_year": end, "claim_ids": [date_claim["claim_id"]],
                           "date_role": "construction_interval_scope_unspecified", "evidence_tier": "reported"})
        comment = str(cells.get("Comment", ""))
        demolition = str(cells.get("Demolition", ""))
        reason = cells.get("Reason") or ("Union of Benefices Act (section classification)" if "Union of Benefices" in section else None)
        partial = section == "Tower remaining"
        text = f"{comment} {demolition}".strip()

        for match in re.finditer(r"[Dd]emolished between (\d{4}) and (\d{4})", text):
            add("partial_demolition" if partial else "demolition", "body", [int(match[1]), int(match[2])],
                "reported_window", reported_reason=reason)
        for match in re.finditer(r"(?<!between )[Dd]emolished in (\d{4})", text):
            add("partial_demolition" if partial or "Body of the church" in text else "demolition", "body",
                [int(match[1])] * 2, "reported_year", reported_reason=reason)
        if re.search(r"\btotally demolished\b", text):
            add("demolition", "body", [None, None], "reported_without_year", reported_reason=reason)
        if re.search(r"[Dd]estroyed in the Blitz", text) or section == "Destroyed in the Blitz":
            add("destruction", "body", [None, None], "reported_blitz_without_year")
        for match in re.finditer(r"(?:[Dd]estroyed|[Rr]uined) in (\d{4})", text):
            add("destruction", "body", [int(match[1])] * 2, "reported_year")
        if re.fullmatch(r"\d{4}", demolition):
            add("demolition", "ruins", [int(demolition)] * 2, "reported_loss_year_scope_unclear")
        roles = {"restored": "restoration_reported", "rededicated": "rededication_milestone",
                 "re-opened": "reopening_milestone", "reconsecrated": "reconsecration_milestone"}
        for match in re.finditer(rf"(restored|rededicated|re-opened|reconsecrated) in {YEAR_RANGE}", text):
            add("restoration", "body", expand_range(match[2], match[3]), roles[match[1]])
        for match in re.finditer(r"restored by (\d{4})", text):
            add("restoration", "body", [None, int(match[1])], "completed_by")
        for match in re.finditer(r"stones transported to ([^.;]+?) in (\d{4})", text):
            add("relocation", "fabric", [int(match[2])] * 2, "reported_year", destination=match[1].strip())
        for match in re.finditer(r"moved to ([A-Z][^.,;]+)", text):
            add("relocation", "tower_and_fittings", [None, None], "reported_without_year", destination=match[1].strip())
        for match in re.finditer(rf"[Rr]ebuilt in {YEAR_RANGE}", text):
            add("rebuilding", "body", expand_range(match[1], match[2]), "later_non_wren_rebuilding")
        for match in re.finditer(r"altered after .*? in (\d{4})", text):
            add("alteration", "body", [int(match[1]), None], "not_before")
        altered = re.search(r"altered in (.+)", text)
        if altered:
            for match in re.finditer(YEAR_RANGE, altered[1]):
                add("alteration", "body", expand_range(match[1], match[2]), "reported_interval")
        if section == "Substantially rebuilt after the Blitz":
            add("damage", "body", [None, None], "section_implied_blitz_damage")
        if text and not found:
            unparsed.append({"church_id": church_id, "text": text})
        for index, row in enumerate(found):
            events.append({"event_id": make_id("event", f"seed:{church_id}:{index}:{row['kind']}"), "church_id": church_id,
                           "claim_ids": [cell_claim["claim_id"]], "evidence_tier": "reported",
                           "reported_text": text, **row})
    return events, unparsed


def listing_agreement(tables: Tables) -> list[Record]:
    seeds = seed_claims(tables)
    listings: dict[str, list[int]] = {}
    for claim in tables["claims"]:
        value = claim.get("value")
        if (claim["field"] != "official_entry_passage" or claim.get("relationship") == "context_only"
                or not isinstance(value, dict) or "Wren" not in value.get("text", "") or claim["subject_id"] in listings):
            continue
        match = LISTING_RANGE.search(value["text"])
        if match:
            listings[claim["subject_id"]] = expand_range(match[1], match[2])
    rows = []
    for church in sorted(tables["churches"], key=lambda row: row["church_id"]):
        seed = seeds.get(church["church_id"], {}).get("seed_date_range", {}).get("value")
        listed = listings.get(church["church_id"])
        status = ("no_seed_range" if not seed else "no_listing_range" if not listed
                  else "agrees" if list(seed) == listed else "differs")
        rows.append({"church_id": church["church_id"], "seed_range": seed, "listing_range": listed, "status": status})
    return rows


BODY_PHASES = {"body", "body_and_steeple"}


def choose_construction(tables: Tables) -> list[Record]:
    claims = {row["claim_id"]: row for row in tables["claims"]}
    publishers = {row["source_id"]: row.get("publisher") for row in tables.get("sources", [])}
    agreement = {row["church_id"]: row for row in listing_agreement(tables)}
    verified = {}
    for event in tables.get("events", []):
        support = [claims.get(identifier) for identifier in event.get("claim_ids", [])]
        if (event["kind"] == "construction" and event.get("phase") in BODY_PHASES
                and event.get("date_role", "construction_interval") == "construction_interval" and support
                and all(claim and claim["review_status"] == "verified" for claim in support)):
            verified[event["church_id"]] = event
    disputed = defaultdict(list)
    catalogue_years = {claim["subject_id"]: claim["value"].get("year") for claim in tables["claims"]
                       if claim["field"] == "parentalia_entry"}
    for claim in tables["claims"]:
        if claim["field"] == "construction_range" and claim["review_status"] == "disputed":
            disputed[claim["subject_id"]].append(claim["value"])
    rows = []
    for church in sorted(tables["churches"], key=lambda row: row["church_id"]):
        identifier = church["church_id"]
        match = agreement[identifier]
        seed = match["seed_range"]
        row = {"church_id": identifier, "name": church["name"], "cohort": church["cohort"], "phase": "scope_unspecified",
               "earliest_year": seed[0] if seed else None, "latest_year": seed[1] if seed else None,
               "alternatives": [], "listing_status": match["status"], "parentalia_year": catalogue_years.get(identifier)}
        if identifier in verified:
            event = verified[identifier]
            row.update(evidence_tier="verified", phase=event["phase"], earliest_year=event["earliest_year"],
                       latest_year=event["latest_year"],
                       verified_source=sorted({publishers.get(claims[c]["source_id"]) or "unknown" for c in event["claim_ids"]}))
            if seed and list(seed) != [event["earliest_year"], event["latest_year"]]:
                row.update(alternatives=[list(seed)],
                           caveat="Verified source interval differs from the seed list range; both kept.")
        elif disputed[identifier] or match["status"] == "differs":
            options = {json.dumps(value) for value in disputed[identifier]}
            if match["status"] == "differs":
                options.add(json.dumps(match["listing_range"]))
            options.discard(json.dumps(list(seed) if seed else None))
            row.update(evidence_tier="disputed", alternatives=sorted((json.loads(value) for value in options), key=json.dumps),
                       caveat="Sources differ; may reflect body/tower/steeple scope or milestone definitions. Unresolved.")
        elif match["status"] == "agrees":
            row.update(evidence_tier="agreeing_sources",
                       caveat="Seed list and heritage listing agree; the list may derive from the listing, so not fully independent.")
        elif seed:
            row["evidence_tier"] = "reported"
        else:
            row["evidence_tier"] = "missing"
        rows.append(row)
    return rows
