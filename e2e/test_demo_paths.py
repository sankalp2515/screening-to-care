"""The reviewer's journey through the live app. Z10–Z12 in docs/evidence/TEST_CASES.md were found by hand on
19 Nov; each has a test here so it cannot come back unnoticed."""

from __future__ import annotations

import re

from conftest import BASE, api, as_persona, case_id
from playwright.sync_api import Page, expect

H1 = "h1"


def test_landing_button_opens_the_tour_on_rajesh(page: Page) -> None:
    page.goto(BASE + "/")
    page.get_by_role("link", name=re.compile("Watch a stalled case get caught")).first.click()
    expect(page).to_have_url(re.compile(r"/app/cases/case_"))
    expect(page.locator(H1)).to_contain_text("Rajesh")
    expect(page.get_by_label("Reviewer tour")).to_contain_text("step 1 of 8")


def test_every_tour_step_opens_its_own_screen(page: Page) -> None:
    """Z10: the last step used to bounce to the role picker; Next used to change only the text."""
    page.goto(BASE + "/demo?tour=1")
    expect(page.locator(H1)).to_contain_text("Rajesh")
    tour = page.get_by_label("Reviewer tour")
    expected = [
        (2, r"/app/cases/", "Rajesh"),
        (3, r"/app/simulator", "watch"),
        (4, r"/app/cases/", "Khalid"),
        (5, r"/app/cases/", "Noura"),
        (6, r"/app/cases/", "Sunita"),
        (7, r"/app/programme", "Programme"),
        (8, r"/patient", "نورة"),
    ]
    for step, path, heading in expected:
        tour.get_by_role("button", name="Next").click()
        expect(tour).to_contain_text(f"step {step} of 8")
        expect(page).to_have_url(re.compile(path))
        expect(page.locator(H1)).to_contain_text(heading)
    tour.get_by_role("button", name="Finish").click()
    expect(page.get_by_label("Reviewer tour")).to_have_count(0)


def test_report_arrives_after_a_false_done_and_clears_the_stall(page: Page) -> None:
    """Z11: on the live API the second scenario stayed locked and lacked the case id."""
    as_persona(page, "dr-fatima", "/app/simulator")
    cards = page.locator("button", has_text="Send to Tasleem")
    expect(cards.nth(1)).to_be_disabled()
    cards.nth(0).click()
    expect(page.get_by_text("Malaffi marked the referral COMPLETED")).to_be_visible()
    expect(cards.nth(1)).to_be_enabled()
    cards.nth(1).click()
    expect(page.get_by_text("The stall clears on evidence")).to_be_visible()
    expect(page.get_by_text("No stalls")).to_be_visible()


def test_reset_demo_resets_the_shared_server(page: Page) -> None:
    """Z12: the button used to clear only the browser cache."""
    before = len(api("/v1/cases?status=all&limit=200")["items"])
    api("/v1/demo/scenarios/false-done", who="dr-fatima", method="POST", body={})
    assert len(api("/v1/cases?status=all&limit=200")["items"]) == before + 1
    page.goto(BASE + "/demo")
    page.get_by_role("button", name="Reset demo").click()
    dialog = page.get_by_role("dialog")
    expect(dialog).to_contain_text("shared")
    dialog.get_by_role("button", name="Reset demo").click()
    expect(page.get_by_text("Demo reset to the starting point.")).to_be_visible(timeout=30_000)  # reseeding takes seconds
    assert len(api("/v1/cases?status=all&limit=200")["items"]) == before


def test_closing_without_evidence_is_blocked_by_r3(page: Page) -> None:
    as_persona(page, "dr-fatima", f"/app/cases/{case_id('Rajesh')}?close=1")
    dialog = page.get_by_role("dialog")
    expect(dialog).to_contain_text("Close this case")
    expect(dialog).to_contain_text("Required clinical evidence has not been received.")
    expect(dialog.locator('[title="R3_EVIDENCE_REQUIRED"]')).to_have_count(1)


def test_a_result_in_a_patient_message_is_refused(page: Page) -> None:
    as_persona(page, "nav-aisha", f"/app/cases/{case_id('Noura')}")
    page.get_by_role("button", name="Message patient").click()
    dialog = page.get_by_role("dialog")
    dialog.get_by_role("textbox").fill("Hello Noura, your result is positive, please rebook.")
    expect(dialog.locator('[title="RESULT_DISCLOSURE"]').first).to_contain_text("Discloses or interprets a result")
    expect(dialog.get_by_role("button", name="Send to patient")).to_be_disabled()


def test_programme_shows_the_national_guideline_scorecard(page: Page) -> None:
    as_persona(page, "coord-sara", "/app/programme")
    expect(page.get_by_role("heading", name="National guideline scorecard")).to_be_visible()
    expect(page.get_by_text("Referred to colonoscopy after a positive FIT")).to_be_visible()
    expect(page.get_by_text("Colonoscopy within 31 working days of referral")).to_be_visible()
    expect(page.get_by_text(re.compile(r"national target|acceptable level|desirable level")).first).to_be_visible()


def test_patient_can_ask_for_a_female_doctor_on_a_phone(phone: Page) -> None:
    as_persona(phone, "p-noura", "/patient")
    expect(phone.locator(H1 + ", header").first).to_contain_text("نورة")
    phone.get_by_role("button", name=re.compile("أخبرنا بما منعك|هناك ما يمنعني")).first.click()
    reasons = phone.locator("fieldset label")
    expect(reasons).to_have_count(6)
    expect(reasons.filter(has_text="طبيبة")).to_have_count(1)


def test_whatsapp_vision_reply_reaches_a_named_navigator(page: Page) -> None:
    """TSL-184: the simulated WhatsApp nudge passes the message policy, and a 'Call me' reply enters the same
    rules as Sahatna, so navigator Aisha gets a call-back task."""
    as_persona(page, "dr-fatima", "/app/simulator")
    chat = page.get_by_label("Simulated WhatsApp chat")
    expect(chat).to_contain_text("نورة")
    expect(page.get_by_text("Passed: no result, no advice, no link")).to_be_visible()
    chat.get_by_role("button", name="اتصلوا بي").click()
    expect(page.get_by_text("Aisha, the navigator, now has a call-back task")).to_be_visible()
    case = api(f"/v1/cases/{case_id('Noura')}")
    assert any("WANTS_CALLBACK" in str(b) and "WhatsApp" in str(b) for b in case["barriers"])


def test_switching_the_draft_language_redrafts_the_message(page: Page) -> None:
    """Found 20 Nov: EN/عربي only flipped the text direction and left the Arabic draft in place."""
    as_persona(page, "dr-fatima", f"/app/cases/{case_id('Ahmed')}")
    box = page.get_by_label("Message to the patient", exact=True)
    expect(box).to_have_value(re.compile(r"[؀-ۿ]"), timeout=40_000)
    page.get_by_role("group", name="Message language").get_by_role("button", name="EN").click()
    expect(box).to_have_value(re.compile(r"^[^؀-ۿ]*[A-Za-z]{4}"), timeout=40_000)
    expect(page.get_by_role("button", name="Send to patient")).to_be_enabled(timeout=20_000)
