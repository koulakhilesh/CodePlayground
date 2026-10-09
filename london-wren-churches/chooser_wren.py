"""Which Wren church? A yes/no chooser built from the reviewed register.

The tree (questions and which sites sit on each leaf) is editorial, in review/chooser.json.
Every site on a leaf carries checks that must hold against the reviewed tables, so a
branch cannot claim weekend hours, a cafe or a step-free entrance the sources don't give.
Writes exports/site/chooser.json (for the website's chooser) and wren-chooser.svg (poster).

Run from the repo root after the pipeline and export_wren_charts.py:
    python london-wren-churches/chooser_wren.py
Then copy exports/site/chooser.json to koulakhilesh.github.io/assets/wren/ and
exports/site/wren-chooser.svg to koulakhilesh.github.io/_includes/wren-chooser.svg.
"""
from __future__ import annotations

from html import escape
import json
from pathlib import Path
from textwrap import wrap

from export_wren_charts import EXPORTS, OUT, church_sites, load, relocation_points

HERE = Path(__file__).resolve().parent
TREE = HERE / "review" / "chooser.json"


def facts(data: dict) -> dict:
    """Per-church facts the checks read, keyed by register name."""
    tables, tiered = data["tables"], data["tiered"]
    names = {c["church_id"]: c["name"] for c in tables["churches"]}
    by_id: dict[str, dict] = {cid: {"church_id": cid, "texts": [], "stepfree": False} for cid in names}
    for row in church_sites(data):
        if row.get("church_id"):
            by_id[row["church_id"]]["section"] = row["section"]
    for row in tiered["visitor_access"]:
        by_id[row["church_id"]].update(scope=row["access_scope"], status=row["published_status"],
                                       opening=" ".join((row.get("opening_text") or "").split()),
                                       url=row.get("url"), checked_at=row["checked_at"])
    for row in tiered["listed_fabric"]:
        by_id[row["church_id"]]["fabric"] = row["fabric_flag"]
    for claim in tables["claims"]:
        if claim["subject_id"] not in by_id:
            continue
        if claim.get("field") == "accessibility":
            by_id[claim["subject_id"]]["stepfree"] = True
        text = claim["value"].get("text") if isinstance(claim["value"], dict) else None
        if text:
            by_id[claim["subject_id"]]["texts"].append(" ".join(text.split()))
    costs = [r for r in tiered["costs"] if r["cohort"] == "parish_replacement"]
    for row in tiered["costs"]:
        by_id[row["church_id"]]["cost"] = round(row["decimal_pounds"])
    if costs:
        by_id[max(costs, key=lambda r: r["decimal_pounds"])["church_id"]]["cost_rank"] = "max"
        by_id[min(costs, key=lambda r: r["decimal_pounds"])["church_id"]]["cost_rank"] = "min"
    for row in relocation_points(data):
        by_id[next(c for c, n in names.items() if n == row["name"])].setdefault("moved", []).append(
            {"to": row["destination"], "km": row["distance_km"]})
    for row in data["graph"]["relocations"]:
        if row["evidence_tier"] == "verified":
            entry = by_id[row["church_id"]]
            entry.setdefault("moved", []).append({"to": row["destination"], "km": None})
            entry.setdefault("moved_urls", []).extend(row["source_urls"])
    return {names[cid]: entry for cid, entry in by_id.items()}


def check_site(site: dict, fact: dict | None, walks: dict) -> list[str]:
    name = site["name"]
    if fact is None:
        return [f"{name}: not in the register"]
    errors = []
    for check in site["checks"]:
        kind = check["kind"]
        if kind == "scope" and fact.get("scope") != check["value"]:
            errors.append(f"{name}: scope {fact.get('scope')!r} is not {check['value']!r}")
        elif kind == "status" and fact.get("status") != check["value"]:
            errors.append(f"{name}: status {fact.get('status')!r} is not {check['value']!r}")
        elif kind == "hours" and (fact.get("status") != "hours_published" or check["quote"] not in fact.get("opening", "")):
            errors.append(f"{name}: no published hours containing {check['quote']!r}")
        elif kind == "section" and fact.get("section") != check["value"]:
            errors.append(f"{name}: list section {fact.get('section')!r} is not {check['value']!r}")
        elif kind == "fabric" and fact.get("fabric") != check["value"]:
            errors.append(f"{name}: listing flag {fact.get('fabric')!r} is not {check['value']!r}")
        elif kind == "stepfree" and not fact["stepfree"]:
            errors.append(f"{name}: no step-free statement on record")
        elif kind == "text" and not any(check["quote"] in text for text in fact["texts"]):
            errors.append(f"{name}: no cached passage contains {check['quote']!r}")
        elif kind == "cost" and (fact.get("cost") != check["amount"] or fact.get("cost_rank") != check.get("rank", fact.get("cost_rank"))):
            errors.append(f"{name}: cost {fact.get('cost')} / rank {fact.get('cost_rank')} does not match {check}")
        elif kind == "moved" and not any(check["to"] in move["to"] and check.get("km") in (None, move["km"])
                                         for move in fact.get("moved", [])):
            errors.append(f"{name}: no verified move to {check['to']!r} ({check.get('km')} km)")
        elif kind == "walk":
            walk = walks.get(check["walk"])
            if not walk or walk["distance_m"] != check["distance_m"] or walk["total_minutes"] != check["total_minutes"]:
                errors.append(f"{name}: walk {check['walk']!r} does not match {check}")
        elif kind not in {"scope", "status", "hours", "section", "fabric", "stepfree", "text", "cost", "moved", "walk"}:
            errors.append(f"{name}: unknown check {kind!r}")
    return errors


def structure_errors(tree: dict) -> list[str]:
    """Every answer leads somewhere, every node is reached exactly once from the start."""
    questions = {q["id"]: q for q in tree["questions"]}
    leaves = {leaf["id"]: leaf for leaf in tree["leaves"]}
    errors, parents = [], {}
    for q in questions.values():
        for answer in ("yes", "no"):
            target = q.get(answer)
            if target not in questions and target not in leaves:
                errors.append(f"{q['id']}: {answer} points to unknown node {target!r}")
            elif target in parents:
                errors.append(f"{target}: reached from both {parents[target]} and {q['id']}")
            else:
                parents[target] = q["id"]
    unreached = (set(questions) | set(leaves)) - set(parents) - {tree["start"]}
    return errors + [f"{node}: not reachable from {tree['start']}" for node in sorted(unreached)]


def validate(tree: dict, facts_by_name: dict, walks: dict) -> list[str]:
    errors = structure_errors(tree)
    for leaf in [*tree["leaves"], tree["aside"]]:
        for site in leaf["sites"]:
            errors += check_site(site, facts_by_name.get(site["name"]), walks)
    return errors


def site_link(site: dict, fact: dict) -> str | None:
    if any(check["kind"] == "moved" for check in site["checks"]):
        urls = fact.get("moved_urls", [])
        return next((u for u in urls if "historicengland" in u or "churchill" in u), urls[0] if urls else None)
    return fact.get("url")


def export_tree(tree: dict, facts_by_name: dict) -> dict:
    def leaf_out(leaf: dict) -> dict:
        return {"id": leaf.get("id"), "title": leaf["title"], "note": leaf.get("note"),
                "sites": [{"name": site.get("label", site["name"]), "why": site["why"],
                           "url": site_link(site, facts_by_name[site["name"]])} for site in leaf["sites"]]}
    checked = sorted({f["checked_at"] for f in facts_by_name.values() if f.get("checked_at")})
    return {"start": tree["start"], "checked_at": checked[-1] if checked else None,
            "questions": {q["id"]: {"text": q["text"], "yes": q["yes"], "no": q["no"]} for q in tree["questions"]},
            "leaves": {leaf["id"]: leaf_out(leaf) for leaf in tree["leaves"]},
            "aside": leaf_out(tree["aside"])}


# Poster layout: questions in a left column (indented when a question has two question
# children), leaves in a right column on the same row as their parent question.
WIDTH, QX, IND, QW, LX, GAP, LINE = 680, 8, 42, 170, 352, 18, 17
SMALL_CHAR = 5.8  # approximate advance of the small body text, in SVG units


def _qbox(text: str) -> tuple[list[str], int]:
    lines = wrap(text, 21)
    return lines, 16 + LINE * len(lines)


def _note_lines(leaf: dict, width: float) -> list[str]:
    return wrap(leaf["note"], int((width - 24) / SMALL_CHAR)) if leaf.get("note") else []


def _site_lines(leaf: dict, width: float) -> list[str]:
    """A one-site leaf titled with that site shows its reason instead of repeating the name."""
    sites = leaf["sites"]
    if len(sites) == 1 and sites[0].get("label", sites[0]["name"]) == leaf["title"]:
        return wrap(sites[0]["why"], int((width - 24) / 6.4))
    return [site.get("label", site["name"]) for site in sites]


def _lbox(leaf: dict, width: float = WIDTH - LX - 8) -> int:
    return 30 + LINE * len(_site_lines(leaf, width)) + 15 * len(_note_lines(leaf, width))


def layout(tree: dict) -> tuple[list[dict], int]:
    questions = {q["id"]: q for q in tree["questions"]}
    leaves = {leaf["id"]: leaf for leaf in tree["leaves"]}
    items: list[dict] = []

    def place(node: str, depth: int, y: int) -> tuple[int, int]:
        """Draw question `node` at row y; return (box top-left y, bottom of its whole subtree)."""
        q = questions[node]
        x = QX + depth * IND
        lines, h = _qbox(q["text"])
        items.append({"type": "q", "x": x, "y": y, "w": QW, "h": h, "lines": lines})
        bottom, leaf_y = y + h, y
        kids = [(answer, q[answer]) for answer in ("yes", "no")]
        for answer, child in kids:
            if child in leaves:
                lh = _lbox(leaves[child])
                items.append({"type": "l", "x": LX, "y": leaf_y, "w": WIDTH - LX - 8, "h": lh, "leaf": leaves[child]})
                items.append({"type": "edge", "answer": answer, "from": (x + QW, y + h / 2 if leaf_y == y else y + h),
                              "to": (LX, leaf_y + 14), "elbow": leaf_y != y})
                leaf_y += lh + GAP / 2
                bottom = max(bottom, leaf_y - GAP / 2)
        sub = [(answer, child) for answer, child in kids if child in questions]
        indent = 1 if len(sub) == 2 else 0
        next_y = bottom + GAP
        for answer, child in sub:
            top, end = place(child, depth + indent, next_y)
            cx = QX + (depth + indent) * IND
            items.append({"type": "edge", "answer": answer, "spine": indent == 1,
                          "from": (x + 13 if indent else x + 30, y + h), "to": (cx if indent else x + 30, top + (13 if indent else 0))})
            next_y = end + GAP
            bottom = end
        return y, bottom

    _, end = place(tree["start"], 0, 40)
    aside = tree["aside"]
    ah = _lbox(aside, WIDTH - 2 * QX)
    items.append({"type": "aside", "x": QX, "y": end + GAP * 2, "w": WIDTH - 2 * QX, "h": ah, "leaf": aside})
    return items, int(end + GAP * 2 + ah + 48)


def poster_svg(tree: dict, source_line: str) -> str:
    items, height = layout(tree)
    out = [f'<svg class="wc-poster" viewBox="0 0 {WIDTH} {height}" role="img" xmlns="http://www.w3.org/2000/svg" '
           f'aria-labelledby="wc-title wc-desc">',
           '<title id="wc-title">Which Wren church should you visit? A yes/no flow chart</title>',
           '<desc id="wc-desc">Start at the top. Yes answers follow the blue lines and no answers the red lines; '
           'each branch ends in a group of churches. The same chart is available as a step-by-step chooser below.</desc>',
           '<text class="wc-start" x="8" y="22">START HERE</text>']
    for item in items:
        if item["type"] == "edge":
            (x1, y1), (x2, y2) = item["from"], item["to"]
            cls = "wc-yes" if item["answer"] == "yes" else "wc-no"
            if item.get("spine"):
                path = f"M{x1},{y1} V{y2} H{x2}"
                lx, ly = x1 + 3, y2 - 5
            elif item.get("elbow"):
                path = f"M{x1 - 24},{y1} V{y2} H{x2}"
                lx, ly = x1 - 18, y2 - 4
            elif x1 == x2:
                path = f"M{x1},{y1} V{y2}"
                lx, ly = x1 + 6, (y1 + y2) / 2 + 4
            else:
                path = f"M{x1},{y1} H{x2 - 20} V{y2} H{x2}"
                lx, ly = x1 + 6, y1 - 4
            out.append(f'<path class="wc-edge {cls}" d="{path}"/>')
            out.append(f'<text class="wc-ans {cls}" x="{lx:.0f}" y="{ly:.0f}">{item["answer"].upper()}</text>')
        elif item["type"] == "q":
            out.append(f'<rect class="wc-q" x="{item["x"]}" y="{item["y"]}" width="{item["w"]}" height="{item["h"]}"/>')
            for i, line in enumerate(item["lines"]):
                out.append(f'<text class="wc-qt" x="{item["x"] + 10}" y="{item["y"] + 21 + i * LINE}">{escape(line)}</text>')
        else:
            leaf, x, y = item["leaf"], item["x"], item["y"]
            cls = "wc-aside" if item["type"] == "aside" else "wc-l"
            out.append(f'<rect class="{cls}" x="{x}" y="{y}" width="{item["w"]}" height="{item["h"]}"/>')
            out.append(f'<rect class="wc-tab" x="{x}" y="{y}" width="4" height="{item["h"]}"/>')
            out.append(f'<text class="wc-lt" x="{x + 12}" y="{y + 19}">{escape(leaf["title"])}</text>')
            ty = y + 19
            for line in _site_lines(leaf, item["w"]):
                ty += LINE
                out.append(f'<text class="wc-ls" x="{x + 12}" y="{ty}">{escape(line)}</text>')
            for line in _note_lines(leaf, item["w"]):
                ty += 15
                out.append(f'<text class="wc-ln" x="{x + 12}" y="{ty + 2}">{escape(line)}</text>')
    for i, line in enumerate(wrap(source_line, int((WIDTH - 16) / SMALL_CHAR))):
        out.append(f'<text class="wc-src" x="8" y="{height - 26 + i * 14}">{escape(line)}</text>')
    out.append("</svg>")
    return "\n".join(out) + "\n"


def main() -> None:
    data = load()
    tree = json.loads(TREE.read_text())
    facts_by_name = facts(data)
    walks = {w["walk_id"]: w for w in json.loads((EXPORTS / "pilot_walks.json").read_text())}
    errors = validate(tree, facts_by_name, walks)
    if errors:
        raise SystemExit("chooser checks failed:\n  " + "\n  ".join(errors))
    exported = export_tree(tree, facts_by_name)
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / "chooser.json").write_text(json.dumps(exported, indent=1, ensure_ascii=False) + "\n", encoding="utf-8")
    source = (f"Data: Friends of the City Churches and church websites (checked {exported['checked_at']}); "
              "Wikipedia (CC BY-SA 4.0); Historic England (OGL v3.0).")
    (OUT / "wren-chooser.svg").write_text(poster_svg(tree, source), encoding="utf-8")
    print("wrote chooser.json and wren-chooser.svg;", sum(len(l["sites"]) for l in tree["leaves"]), "leaf entries checked")


if __name__ == "__main__":
    main()
