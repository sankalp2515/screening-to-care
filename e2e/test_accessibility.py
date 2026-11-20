"""WCAG 2.1 AA checks with axe-core on the screens reviewers and patients use most (TSL-177).
Serious and critical violations fail the build; minor and moderate ones are printed for the backlog."""

from __future__ import annotations

import pytest
from conftest import BASE, as_persona, case_id
from playwright.sync_api import Page

AXE = "https://cdnjs.cloudflare.com/ajax/libs/axe-core/4.10.2/axe.min.js"
RULES = {"runOnly": {"type": "tag", "values": ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa"]}}


def audit(page: Page) -> list[dict]:
    page.wait_for_load_state("networkidle")
    page.wait_for_timeout(300)
    # Entrance animations (the hero's three beats end near 2.3 s) must finish, so contrast is measured on final colours.
    page.evaluate("() => Promise.all(document.getAnimations().map(a => a.finished.catch(() => null)))")
    page.add_script_tag(url=AXE)
    result = page.evaluate("opts => axe.run(document, opts)", RULES)
    for v in result["violations"]:
        print(f"{v['impact']:>9}  {v['id']}: {len(v['nodes'])} node(s) · {v['help']}")
    return [v for v in result["violations"] if v["impact"] in ("serious", "critical")]


@pytest.mark.parametrize("persona,path", [
    (None, "/"),
    (None, "/demo"),
    ("dr-fatima", "/app/work"),
    ("dr-fatima", "CASE:Rajesh"),
    ("coord-sara", "/app/programme"),
])
def test_no_serious_accessibility_violations(page: Page, persona: str | None, path: str) -> None:
    if path.startswith("CASE:"):
        path = f"/app/cases/{case_id(path[5:])}"
    if persona:
        as_persona(page, persona, path)
    else:
        page.goto(BASE + path)
    bad = audit(page)
    assert not bad, [(v["id"], v["help"], [n["target"] for n in v["nodes"][:3]]) for v in bad]


def test_patient_screen_in_arabic_has_no_serious_violations(phone: Page) -> None:
    as_persona(phone, "p-noura", "/patient")
    bad = audit(phone)
    assert not bad, [(v["id"], v["help"], [n["target"] for n in v["nodes"][:3]]) for v in bad]
