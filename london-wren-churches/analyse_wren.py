import argparse
from collections import Counter
import csv
from html import escape
import json
from pathlib import Path
import re
from textwrap import wrap

import plotly.graph_objects as go

from collect_wren import write_json
from tiers_wren import choose_construction, seed_claims
from wren_records import Record, Tables

COHORT_LABELS = {
    "parish_replacement": "Post-fire replacement / substantial rebuilding",
    "parish_repair": "Post-fire repair / partial reconstruction",
    "parish_nonfire_rebuilding": "Rebuilding of a fire survivor",
    "cathedral": "Cathedral", "refurbishment": "Interior refurbishment",
    "outside_fire_area": "Outside fire area", "unresolved": "Attribution unresolved",
    "excluded": "Excluded", "related_site": "Related site (not a church)",
}
COLORS = {"parish_replacement": "#007f73", "parish_repair": "#bd562a",
          "parish_nonfire_rebuilding": "#586b31", "cathedral": "#242424",
          "refurbishment": "#ad3864", "outside_fire_area": "#3578a4",
          "unresolved": "#666666", "excluded": "#aaaaaa", "related_site": "#c79a00"}
TIER_COLORS = {"verified": "#007f73", "agreeing_sources": "#3578a4", "disputed": "#bd562a", "reported": "#8a8a8a"}
LOSS_KINDS = {"demolition", "partial_demolition", "destruction"}
FABRIC_PHRASES = [
    (re.compile(r"(interior|church)[^.]{0,40}(destroyed|burnt|burned|gutted)[^.]{0,60}(reconstructed|rebuilt)[^.]{0,20}facsimile", re.I),
     "interior_reconstructed_in_facsimile"),
    (re.compile(r"(damaged|bombed)[^.]{0,40}(World War II|war)[^.]{0,40}restored", re.I), "war_damaged_and_restored"),
    (re.compile(r"(extensively|largely) reconstructed after World War II", re.I), "extensively_reconstructed_postwar"),
    (re.compile(r"(body of (the )?church|church body)[^.]{0,30}(destroyed|demolished)", re.I), "body_lost"),
]


def listed_fabric(tables: Tables) -> list[Record]:
    churches = {church["church_id"]: church for church in tables["churches"]}
    found: dict[str, Record] = {}
    for claim in tables["claims"]:
        value = claim.get("value")
        if (claim["field"] != "official_entry_passage" or claim.get("relationship") == "context_only"
                or claim["subject_id"] not in churches or not isinstance(value, dict) or "Wren" not in value.get("text", "")):
            continue
        for pattern, label in FABRIC_PHRASES:
            match = pattern.search(value["text"])
            if match and claim["subject_id"] not in found:
                found[claim["subject_id"]] = {"church_id": claim["subject_id"], "name": churches[claim["subject_id"]]["name"],
                                              "fabric_flag": label, "phrase": " ".join(match.group(0).split()),
                                              "claim_id": claim["claim_id"], "evidence_tier": "official_listing_phrase"}
                break
    return sorted(found.values(), key=lambda row: row["name"])


def loss_mechanism(event: Record) -> str:
    if event.get("mechanism"):
        return event["mechanism"]
    if event["kind"] == "destruction":
        return "war_destruction"
    reason = str(event.get("reported_reason") or "")
    if "Union of Benefices" in reason:
        return "union_of_benefices"
    if "unsafe" in reason:
        return "structural_safety"
    if reason:
        return "site_clearance_or_street_works"
    return "reason_not_stated"


def tiered_history(tables: Tables) -> Tables:
    """Coverage-complete history where every row carries its evidence tier."""
    churches = {church["church_id"]: church for church in tables["churches"]}
    claims = {claim["claim_id"]: claim for claim in tables["claims"]}
    construction = [row for row in choose_construction(tables) if row["cohort"] == "parish_replacement"]
    losses = []
    for event in sorted(tables.get("events", []), key=lambda row: row["event_id"]):
        church = churches.get(event["church_id"])
        if not church or event["kind"] not in LOSS_KINDS:
            continue
        support = [claims.get(identifier) for identifier in event.get("claim_ids", [])]
        tier = ("verified" if support and all(claim and claim["review_status"] == "verified" for claim in support)
                else event.get("evidence_tier", "reported"))
        losses.append({"church_id": event["church_id"], "name": church["name"], "cohort": church["cohort"],
                       "kind": event["kind"], "phase": event.get("phase"), "earliest_year": event.get("earliest_year"),
                       "latest_year": event.get("latest_year"), "mechanism": loss_mechanism(event),
                       "mechanism_basis": "reviewed_passage" if event.get("reason_claim_ids") else "seed_classification",
                       "reported_reason": event.get("reported_reason"), "evidence_tier": tier})
    strongest: dict[tuple, Record] = {}
    for row in losses:
        key = (row["church_id"], row["kind"], row["earliest_year"], row["latest_year"])
        if key not in strongest or (row["evidence_tier"] == "verified" and strongest[key]["evidence_tier"] != "verified"):
            strongest[key] = row
    losses = list(strongest.values())
    # An undated seed loss restates a dated loss with the same reviewed cause (e.g. a 1940 bombing).
    dated = {(row["church_id"], row["mechanism"]) for row in losses if row["earliest_year"]}
    losses = [row for row in losses if row["earliest_year"] or (row["church_id"], row["mechanism"]) not in dated]
    sections = {identifier: rows.get("seed_section", {}).get("value", "not_listed")
                for identifier, rows in seed_claims(tables).items()}
    survival = Counter((sections.get(identifier, "not_listed"), church["cohort"]) for identifier, church in churches.items())
    access = sorted(({"church_id": row["church_id"], "name": churches[row["church_id"]]["name"],
                      "access_scope": row["access_scope"], "published_status": row["published_status"],
                      "opening_text": row.get("opening_text"), "checked_at": row["checked_at"], "url": row["url"],
                      "evidence_tier": row["evidence_tier"]}
                     for row in tables.get("visitor_listings", []) if row.get("church_id") in churches),
                    key=lambda row: row["name"])
    return {
        "construction": construction,
        "construction_tiers": dict(sorted(Counter(row["evidence_tier"] for row in construction).items())),
        "losses": losses,
        "losses_by_mechanism": dict(sorted(Counter(row["mechanism"] for row in losses).items())),
        "losses_by_tier": dict(sorted(Counter(row["evidence_tier"] for row in losses).items())),
        "survival": [{"seed_section": section, "cohort": cohort, "count": count}
                     for (section, cohort), count in sorted(survival.items())],
        "population": sorted(tables.get("population", []), key=lambda row: row["year"]),
        "visitor_access": access,
        "listed_fabric": listed_fabric(tables),
        "costs": sorted(({"church_id": claim["subject_id"], "name": churches[claim["subject_id"]]["name"],
                          "cohort": churches[claim["subject_id"]]["cohort"], **claim["value"]}
                         for claim in tables["claims"] if claim["field"] == "construction_cost"
                         and claim["review_status"] == "verified" and claim["subject_id"] in churches),
                        key=lambda row: -row["decimal_pounds"]),
        "visitor_access_counts": dict(sorted(Counter(f"{row['access_scope']}/{row['published_status']}" for row in access).items())),
        "no_visitor_listing_ids": sorted(set(churches) - {row["church_id"] for row in access}),
        "tier_definitions": {
            "verified": "Reviewed against a recorded source with rationale",
            "agreeing_sources": "Seed list and heritage listing agree; possibly not independent",
            "disputed": "Sources give different ranges; all kept, none chosen",
            "reported": "Single secondary list (Wikipedia seed); unreviewed",
        },
    }


def construction_figure(rows: list[Record]) -> go.Figure:
    figure = go.Figure()
    for tier, color in TIER_COLORS.items():
        selected = [row for row in rows if row["evidence_tier"] == tier and row["earliest_year"] is not None]
        if not selected:
            continue
        figure.add_trace(go.Bar(
            x=[row["latest_year"] - row["earliest_year"] or 0.4 for row in selected],
            base=[row["earliest_year"] for row in selected], y=[escape(row["name"]) for row in selected],
            orientation="h", name=tier.replace("_", " "), marker={"color": color},
            customdata=[[row["earliest_year"], row["latest_year"], escape(str(row.get("alternatives") or ""))] for row in selected],
            hovertemplate="<b>%{y}</b><br>%{customdata[0]}-%{customdata[1]}<br>Alternatives: %{customdata[2]}<extra>%{fullData.name}</extra>"))
    figure.update_layout(barmode="overlay", xaxis_title="Reported year", template="plotly_white",
                         yaxis={"automargin": True, "categoryorder": "array", "tickfont": {"size": 11},
                                "categoryarray": [escape(row["name"]) for row in sorted(rows, key=lambda r: (r["earliest_year"] or 9999), reverse=True)]},
                         height=max(500, 22 * len(rows) + 160), margin={"l": 20, "r": 20, "t": 20, "b": 55},
                         legend={"orientation": "h", "y": -0.06}, font={"family": "Georgia", "size": 13})
    return figure


def losses_figure(losses: list[Record], population: list[Record] | None = None) -> go.Figure:
    figure = go.Figure()
    census = [row for row in population or [] if row.get("count_type") == "census" and row["year"] <= 1971]
    if census:
        figure.add_trace(go.Scatter(x=[row["year"] for row in census], y=[row["population"] for row in census],
                                    mode="lines+markers", name="Resident population (census)", yaxis="y2",
                                    line={"color": "#b9b9b9", "width": 2}, marker={"size": 5},
                                    hovertemplate="%{x}: %{y:,} residents<extra></extra>"))
    dated = [row for row in losses if row["earliest_year"] is not None]
    for mechanism in sorted({row["mechanism"] for row in dated}):
        selected = [row for row in dated if row["mechanism"] == mechanism]
        label = "<br>".join(wrap(mechanism.replace("_", " "), width=14))
        figure.add_trace(go.Scatter(
            x=[row["earliest_year"] for row in selected], y=[label] * len(selected),
            mode="markers", name=mechanism.replace("_", " "),
            marker={"size": 12, "symbol": ["circle" if row["evidence_tier"] == "verified" else "circle-open" for row in selected]},
            text=[escape(f"{row['name']} - {row['kind']} ({row['evidence_tier']})") for row in selected],
            hovertemplate="%{text}<br>%{x}<extra></extra>"))
    figure.update_layout(xaxis_title="Reported year", template="plotly_white",
                         showlegend=bool(census), legend={"orientation": "h", "y": -0.28, "x": 0},
                         yaxis={"automargin": True, "tickfont": {"size": 11}},
                         yaxis2={"overlaying": "y", "side": "right", "title": "Residents", "showgrid": False,
                                 "rangemode": "tozero"} if census else None,
                         height=520, margin={"l": 10, "r": 10, "t": 20, "b": 110},
                         font={"family": "Georgia", "size": 13})
    return figure


def summarise_history(tables: Tables) -> Tables:
    churches = {church["church_id"]: church for church in tables["churches"]}
    claims = {claim["claim_id"]: claim for claim in tables["claims"]}
    summary: Tables = {"starts": [], "completions": [], "durations": [], "losses": [], "timeline": []}
    for event in sorted(tables.get("events", []), key=lambda row: row["event_id"]):
        church = churches.get(event["church_id"])
        supporting = [claims.get(identifier) for identifier in event.get("claim_ids", [])]
        if not church or not supporting or any(
            claim is None or claim["review_status"] != "verified" or claim["subject_id"] != event["church_id"]
            for claim in supporting
        ):
            continue
        earliest, latest = event.get("earliest_year"), event.get("latest_year")
        if type(earliest) is not int or type(latest) is not int or earliest > latest:
            continue
        row = {**event, "name": church["name"], "cohort": church["cohort"], "evidence_status": "verified"}
        summary["timeline"].append(row)
        if church["cohort"] != "parish_replacement":
            continue
        if (event["kind"] == "construction" and event.get("phase") == "body"
            and event.get("date_role", "construction_interval") == "construction_interval"):
            summary["starts"].append({"year": earliest, "church_id": event["church_id"], "event_id": event["event_id"]})
            summary["completions"].append({"year": latest, "church_id": event["church_id"], "event_id": event["event_id"]})
            summary["durations"].append({"church_id": event["church_id"], "event_id": event["event_id"],
                                         "elapsed_years": latest - earliest, "phase": "body",
                                         "interpretation": "Elapsed interval, not continuous labour time"})
        elif event["kind"] in {"demolition", "partial_demolition"}:
            summary["losses"].append(row)
    return summary


def build_map_points(tables: Tables) -> list[Record]:
    churches = {church["church_id"]: church for church in tables["churches"]}
    claims = {claim["claim_id"]: claim for claim in tables["claims"]}
    sources = {source["source_id"]: source for source in tables["sources"]}
    points = []
    seen = set()
    for place in sorted(tables.get("places", []), key=lambda row: row["place_id"]):
        church = churches.get(place.get("church_id"))
        latitude, longitude = place.get("latitude"), place.get("longitude")
        if not church or latitude is None or longitude is None:
            continue
        key = (church["church_id"], place["role"], latitude, longitude)
        if key in seen:
            continue
        seen.add(key)
        evidence = [claims.get(identifier) for identifier in place.get("claim_ids", [])]
        status = "verified" if evidence and all(claim and claim["review_status"] == "verified" for claim in evidence) else "extracted"
        urls = sorted({sources[claim["source_id"]]["url"] for claim in evidence if claim and claim["source_id"] in sources})
        points.append({**place, "name": church["name"], "cohort": church["cohort"],
                       "wren_work": church.get("wren_work", "not_yet_scoped"),
                       "location_status": status, "source_urls": urls})
    for site in sorted(tables.get("related_sites", []), key=lambda row: row["site_id"]):
        if site.get("latitude") is None or site.get("longitude") is None:
            continue
        points.append({"place_id": site["site_id"], "church_id": None, "name": site["name"], "cohort": "related_site",
                       "role": site["role"], "latitude": site["latitude"], "longitude": site["longitude"],
                       "wren_work": site.get("caveat", ""), "location_status": site.get("evidence_tier", "reported"),
                       "source_urls": [site["article_url"]]})
    return points


def map_figure(points: list[Record]) -> go.Figure:
    figure = go.Figure()
    for cohort, label in COHORT_LABELS.items():
        selected = [point for point in points if point["cohort"] == cohort]
        if not selected:
            continue
        figure.add_trace(go.Scattermap(
            lat=[point["latitude"] for point in selected], lon=[point["longitude"] for point in selected],
            mode="markers", name=label, marker={"size": 12, "color": COLORS[cohort]},
            text=[escape(point["name"]) for point in selected],
            customdata=[[escape(point["role"]), point["location_status"], escape(point["wren_work"])] for point in selected],
            hovertemplate="<b>%{text}</b><br>%{customdata[2]}<br>Location: %{customdata[0]} (%{customdata[1]})<extra>%{fullData.name}</extra>",
        ))
    figure.update_layout(map={"style": "open-street-map", "center": {"lat": 51.511, "lon": -0.105}, "zoom": 12},
                         height=760, margin={"l": 10, "r": 10, "t": 20, "b": 20},
                         legend={"orientation": "h", "y": -0.05}, font={"family": "Georgia", "size": 13})
    return figure


def timeline_figure(events: list[Record]) -> go.Figure:
    figure = go.Figure()
    for event in events:
        earliest, latest = event["earliest_year"], event["latest_year"]
        label = "<br>".join(escape(part) for part in wrap(event["name"], width=22)) + "<br>" + escape(event.get("phase", "unspecified")) + " - " + escape(event["kind"])
        figure.add_trace(go.Scatter(x=[earliest, latest] if earliest != latest else [earliest],
                                   y=[label, label] if earliest != latest else [label], mode="lines+markers",
                                   line={"width": 5, "color": COLORS.get(event["cohort"], "#666666")},
                                   marker={"size": 10}, name=label,
                                   text=[escape(event.get("date_basis", "Reviewed event"))] * (2 if earliest != latest else 1),
                                   hovertemplate="%{y}<br>%{x}<br>%{text}<extra></extra>", showlegend=False))
    if not events:
        figure.add_annotation(text="No verified dated events available", x=0.5, y=0.5, xref="paper", yref="paper", showarrow=False)
    figure.update_layout(xaxis_title="Reported year",
                         yaxis={"automargin": True, "tickfont": {"size": 11}}, height=max(430, 80 * len(events) + 160),
                         margin={"l": 20, "r": 20, "t": 20, "b": 55},
                         template="plotly_white", font={"family": "Georgia", "size": 13})
    return figure


def write_chart(figure: go.Figure, path: Path, title: str, caption: str, chart_id: str) -> None:
    chart = figure.to_html(full_html=False, include_plotlyjs=True, div_id=chart_id,
                           config={"responsive": True, "displaylogo": False})
    document = f'''<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>{escape(title)}</title><style>
body {{ margin: 0; color: #262626; background: #fafafa; font-family: Georgia, serif; }}
main {{ max-width: 1280px; margin: auto; padding: 16px; }}
header {{ border-bottom: 1px solid #cccccc; padding-bottom: 12px; }}
h1 {{ font-size: 24px; line-height: 1.2; margin: 0 0 12px; overflow-wrap: anywhere; }}
p {{ font-size: 15px; line-height: 1.5; margin: 0; max-width: 80ch; }}
.js-plotly-plot {{ width: 100%; }}
</style></head><body><main><header><h1>{escape(title)}</h1><p>{escape(caption)}</p></header>{chart}</main></body></html>
'''
    path.write_text(document, encoding="utf-8")


def write_analysis(tables: Tables, output_dir: Path) -> list[Path]:
    output_dir.mkdir(parents=True, exist_ok=True)
    history = summarise_history(tables)
    tiered = tiered_history(tables)
    points = build_map_points(tables)
    summary = {"candidate_count": len(tables["churches"]),
               "cohorts": dict(sorted(Counter(church["cohort"] for church in tables["churches"]).items())),
               "reviewed_event_count": len(history["timeline"]), "map_point_count": len(points),
               "history": history, "tiered": tiered,
               "limitations": ["Operational cohorts do not resolve traditional 51-church count.",
                               "Source-supported identity is not independent date verification.",
                               "Map coordinates are source-reported historical sites, not verified entrances.",
                               "Timeline has partial reviewed coverage; do not infer missing events or city-wide rates."]}
    paths = [output_dir / name for name in ("analysis_summary.json", "map_points.json", "church_register.csv", "cohort_map.html",
                                            "reviewed_timeline.html", "construction_tiers.html", "losses.html")]
    write_json(paths[0], summary)
    write_json(paths[1], points)
    point_lookup = {point["church_id"]: point for point in points if point.get("church_id")}
    access_lookup = {row["church_id"]: row for row in tiered["visitor_access"]}
    construction_lookup = {row["church_id"]: row for row in choose_construction(tables)}
    with paths[2].open("w", newline="", encoding="utf-8") as stream:
        columns = ["church_id", "name", "cohort", "wren_work", "latitude", "longitude", "location_status", "identity_rationale", "article_url",
                   "construction_earliest", "construction_latest", "construction_tier", "access_scope", "published_status", "access_checked_at"]
        writer = csv.DictWriter(stream, fieldnames=columns)
        writer.writeheader()
        for church in sorted(tables["churches"], key=lambda row: row["name"]):
            point = point_lookup.get(church["church_id"], {})
            access = access_lookup.get(church["church_id"], {})
            built = construction_lookup.get(church["church_id"], {})
            extra = {"construction_earliest": built.get("earliest_year"), "construction_latest": built.get("latest_year"),
                     "construction_tier": built.get("evidence_tier"), "access_scope": access.get("access_scope"),
                     "published_status": access.get("published_status"), "access_checked_at": access.get("checked_at")}
            writer.writerow({column: extra.get(column, church.get(column, point.get(column, ""))) for column in columns})
    write_chart(map_figure(points), paths[3], "Wren-associated sites",
                "Exploratory cohort map. Source-reported locations, not visitor entrances. Dates, access and original fabric are not verified by this map.", "wren-cohort-map")
    write_chart(timeline_figure(history["timeline"]), paths[4], "Reviewed event timeline",
                "Partial coverage only. These are reviewed construction and loss events, not all church histories. Intervals retain their recorded scope; elapsed spans are not continuous labour time.", "wren-reviewed-timeline")
    write_chart(construction_figure(tiered["construction"]), paths[5], "Rebuilding intervals by evidence tier",
                "Post-fire replacement parish churches. Colour shows evidence strength: verified, two sources agreeing (possibly not independent), disputed (alternatives in hover) or reported by one secondary list. Scope (body, tower, steeple) is unspecified unless verified.", "wren-construction-tiers")
    write_chart(losses_figure(tiered["losses"], tiered["population"]), paths[6], "How the churches were lost",
                "Reported demolitions and wartime destruction by mechanism, plotted at the first year of any reported window. Filled markers are verified; open markers are reported by a secondary list. Undated losses are omitted from the chart but kept in the data. Grey line: resident census population of the City (Wikipedia table citing City of London Corporation / ONS; 1941 had no census and is omitted). Population is context, not a tested cause.", "wren-losses")
    return paths


def main() -> None:
    parser = argparse.ArgumentParser(description="Export evidence-labelled Wren exploratory research charts")
    parser.add_argument("--data", type=Path, default=Path("data/london_wren_churches"))
    parser.add_argument("--output", type=Path, default=Path("london-wren-churches/exports"))
    args = parser.parse_args()
    tables = json.loads((args.data / "tables_reviewed.json").read_text())
    paths = write_analysis(tables, args.output)
    print(json.dumps({"exports": [str(path) for path in paths], "verified_events": len(summarise_history(tables)["timeline"])}, indent=2))


if __name__ == "__main__":
    main()