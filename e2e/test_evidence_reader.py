"""A1 Evidence Reader in the browser: a report that says "incomplete" is read, quoted, confirmed by the physician,
and the rules keep the loop open. Uses a fresh simulator case so it can run again on the shared server."""

from __future__ import annotations

import re

from conftest import BASE, api, as_persona
from playwright.sync_api import Page, expect


def test_physician_confirms_an_incomplete_report_and_the_case_stays_open(page: Page) -> None:
    cid = api("/v1/demo/scenarios/incomplete-report", who="dr-fatima", method="POST", body={})["case_id"]
    as_persona(page, "dr-fatima", f"/app/cases/{cid}")
    card = page.get_by_role("region", name="Colonoscopy report")
    expect(card).to_contain_text("A report arriving does not close the loop")
    # Each reading quotes its sentence, highlighted in the report itself.
    expect(card.locator("mark").first).to_be_visible()
    expect(card).to_contain_text("poor bowel preparation", timeout=40_000)
    expect(card.get_by_role("button", name=re.compile("Confirm"))).to_be_enabled(timeout=40_000)
    card.get_by_role("button", name=re.compile("Confirm")).click()
    expect(page.get_by_text("The case stays open: the colonoscopy must be rebooked")).to_be_visible()
    expect(page.get_by_role("heading", name="Colonoscopy incomplete: rebook")).to_be_visible()
    close = {c["outcome"]: c for c in api(f"/v1/cases/{cid}", who="dr-fatima")["actions"]["close"]}
    assert close["COMPLETED_WITH_REPORT"]["code"] == "R3_PROCEDURE_INCOMPLETE"


def test_a_navigator_cannot_confirm_a_report(page: Page) -> None:
    cid = api("/v1/demo/scenarios/incomplete-report", who="dr-fatima", method="POST", body={})["case_id"]
    as_persona(page, "nav-aisha", f"/app/cases/{cid}")
    card = page.get_by_role("region", name="Colonoscopy report")
    expect(card.get_by_text("Only a physician can confirm what a report says.")).to_be_visible(timeout=40_000)


def test_usage_tab_loads(page: Page) -> None:
    """Judge finding, 20 Nov: Programme → Usage showed 'VALIDATION Request validation failed' (missing month)."""
    as_persona(page, "coord-sara", "/app/programme")
    page.get_by_role("tab", name="Usage").click()
    expect(page.get_by_text("Request validation failed")).to_have_count(0)
