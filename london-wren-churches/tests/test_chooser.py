import json
from pathlib import Path

import pytest

from chooser_wren import check_site, poster_svg, structure_errors

TREE = json.loads((Path(__file__).resolve().parents[1] / "review" / "chooser.json").read_text())


def fact(**extra):
    return {"texts": [], "stepfree": False, **extra}


def test_reviewed_tree_is_a_complete_tree():
    assert structure_errors(TREE) == []


def test_structure_catches_dangling_shared_and_orphan_nodes():
    tree = {"start": "a", "questions": [{"id": "a", "text": "?", "yes": "l1", "no": "nowhere"},
                                        {"id": "b", "text": "?", "yes": "l1", "no": "l2"}],
            "leaves": [{"id": "l1"}, {"id": "l2"}]}
    errors = structure_errors(tree)
    assert any("unknown node 'nowhere'" in e for e in errors)
    assert any("l1: reached from both" in e for e in errors)
    assert any("b: not reachable" in e for e in errors)


@pytest.mark.parametrize("check,good,bad", [
    ({"kind": "hours", "quote": "Sat 10am"}, fact(status="hours_published", opening="Mon-Fri, Sat 10am"),
     fact(status="closure_notice", opening="Sat 10am")),
    ({"kind": "scope", "value": "tower"}, fact(scope="tower"), fact(scope="interior")),
    ({"kind": "stepfree"}, fact(stepfree=True), fact()),
    ({"kind": "text", "quote": "cafe known as The Wren"}, fact(texts=["a supporting cafe known as The Wren."]), fact()),
    ({"kind": "cost", "amount": 1854, "rank": "min"}, fact(cost=1854, cost_rank="min"), fact(cost=1854, cost_rank="max")),
    ({"kind": "moved", "to": "Sydenham", "km": 8.8}, fact(moved=[{"to": "Round Hill, Sydenham", "km": 8.8}]),
     fact(moved=[{"to": "Round Hill, Sydenham", "km": 9.1}])),
])
def test_each_check_passes_only_when_the_data_supports_it(check, good, bad):
    site = {"name": "X", "checks": [check]}
    assert check_site(site, good, {}) == []
    assert check_site(site, bad, {}) != []


def test_site_missing_from_register_is_an_error():
    assert check_site({"name": "Nowhere", "checks": []}, None, {}) == ["Nowhere: not in the register"]


def test_poster_escapes_text_and_keeps_every_leaf():
    svg = poster_svg(TREE, "Data: A & B")
    assert "Data: A &amp; B" in svg and svg.startswith("<svg")
    for leaf in TREE["leaves"]:
        assert leaf["title"].replace("'", "&#x27;") in svg
