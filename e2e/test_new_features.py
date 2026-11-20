"""Browser tests for the 19 Nov backlog: cover while away, the unmatched queue, the repeat-FIT guard, the female
endoscopist routing, the patient's calendar and read-aloud helpers, and the programme export."""

from __future__ import annotations

import re

from conftest import api, as_persona, case_id
from playwright.sync_api import Page, expect


def test_cover_shows_in_the_covering_doctors_work_list(page: Page) -> None:
    """TSL-160: Dr. Omar is away; Dr. Lina sees his question in her list and knows she is covering."""
    as_persona(page, "dr-lina", "/app/work")
    expect(page.get_by_role("status")).to_contain_text("You are covering for Dr. Omar")
    expect(page.get_by_text("Ahmed S.").first).to_be_visible()


def test_a_coordinator_matches_an_unknown_record_and_a_case_opens(page: Page) -> None:
    """TSL-161: the lab sent a positive FIT under a record number nobody knows; it waits for a person."""
    as_persona(page, "coord-sara", "/app/programme")
    page.get_by_role("tab", name="Unmatched").click()
    expect(page.get_by_text("record mrn-skmc-88213")).to_be_visible()
    page.get_by_label("Patient").first.select_option(label="Khalfan B. (51)")
    page.get_by_role("button", name="Match").first.click()
    expect(page.get_by_text("A case opened with a named owner.")).to_be_visible()
    assert api("/v1/integration/unmatched")["count"] == 0


def test_a_negative_repeat_fit_keeps_the_case_open_with_a_warning(page: Page) -> None:
    """TSL-163: a negative repeat FIT never cancels the colonoscopy."""
    as_persona(page, "dr-fatima", "/app/simulator")
    page.locator('[data-scenario="repeat-fit-negative"]').get_by_role("button", name="Send to Tasleem").click()
    expect(page.get_by_text("does not cancel the colonoscopy")).to_be_visible()
    page.get_by_role("button", name="Open case").click()
    expect(page.get_by_label("Rule warnings")).to_contain_text("does not cancel the colonoscopy")


def test_referral_options_put_a_female_endoscopist_first_once_asked(page: Page) -> None:
    """TSL-165: after the patient asks for a female doctor, the GI centre with one is marked and listed first."""
    cid = case_id("Noura")
    api(f"/v1/cases/{cid}/barriers", who="p-noura", method="POST", body={"codes": ["FEMALE_CLINICIAN"]})
    as_persona(page, "dr-fatima", f"/app/cases/{cid}")
    page.get_by_role("button", name="More…").click()
    page.get_by_role("button", name="Referral options").click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_contain_text("asked for a female doctor")
    expect(dialog.get_by_role("listitem").first).to_contain_text("Female endoscopist")


def test_patient_with_an_appointment_can_add_it_and_hear_the_step(phone: Page) -> None:
    """TSL-183 and TSL-178: calendar, escort request and read-aloud on the patient's phone."""
    as_persona(phone, "p-yousef", "/patient")
    expect(phone.get_by_role("button", name=re.compile("استمع|Listen"))).to_be_visible()
    expect(phone.get_by_role("button", name=re.compile("أضف إلى تقويمي|Add to my calendar"))).to_be_visible()
    expect(phone.get_by_role("button", name=re.compile("اطلب من أحد أن يرافقني|Ask someone to come with me"))).to_be_visible()


def test_programme_lead_can_download_the_csv(page: Page) -> None:
    """TSL-182: pseudonymous export for the programme's own reporting."""
    as_persona(page, "coord-sara", "/app/programme")
    with page.expect_download() as dl:
        page.get_by_role("button", name="Download CSV").click()
    path = dl.value.path()
    text = open(path, encoding="utf-8").read()
    assert text.startswith("case_id,patient_ref,pathway") and "Rajesh" not in text
