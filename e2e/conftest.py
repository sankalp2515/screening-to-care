"""Browser end-to-end tests (TSL-176): drive the real web app against a running stack, as a reviewer would.

Run against the local Docker stack (default) or the live demo:
    E2E_BASE_URL=https://tasleem.swedencentral.cloudapp.azure.com python -m pytest e2e -q
Locally on Windows without Playwright's own browser: set E2E_CHANNEL=msedge.
Every test starts from the clean synthetic seed, and the seed is restored at the end.
"""

from __future__ import annotations

import json
import os
import urllib.request
from collections.abc import Iterator

import pytest
from playwright.sync_api import Browser, Page, sync_playwright

BASE = os.environ.get("E2E_BASE_URL", "http://localhost:8080").rstrip("/")
CHANNEL = os.environ.get("E2E_CHANNEL") or None


def api(path: str, who: str = "coord-sara", method: str = "GET", body: dict | None = None) -> dict:
    data = json.dumps(body).encode() if body is not None else None
    req = urllib.request.Request(f"{BASE}/api/core{path}", data=data, method=method,
                                 headers={"X-Demo-User": who, "Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=60) as r:
        return json.load(r)


def reset() -> None:
    api("/v1/admin/reset-demo", method="POST")


@pytest.fixture(scope="session")
def browser() -> Iterator[Browser]:
    with sync_playwright() as p:
        b = p.chromium.launch(channel=CHANNEL)
        yield b
        b.close()
    reset()


@pytest.fixture()
def page(browser: Browser) -> Iterator[Page]:
    reset()
    ctx = browser.new_context(viewport={"width": 1440, "height": 900})
    pg = ctx.new_page()
    pg.set_default_timeout(20_000)
    yield pg
    ctx.close()


@pytest.fixture()
def phone(browser: Browser) -> Iterator[Page]:
    reset()
    ctx = browser.new_context(viewport={"width": 375, "height": 812}, is_mobile=True, has_touch=True)
    pg = ctx.new_page()
    pg.set_default_timeout(20_000)
    yield pg
    ctx.close()


def as_persona(page: Page, persona: str, path: str) -> None:
    """Open the app as a demo persona, the way the role picker does, then go to `path`."""
    page.goto(f"{BASE}/demo")
    page.evaluate("""p => { localStorage.setItem('tasleem.persona', p);
                          localStorage.setItem('tasleem.tour', JSON.stringify({open: false, step: 0})); }""", persona)
    page.goto(f"{BASE}{path}")


def case_id(patient_first_name: str, who: str = "coord-sara") -> str:
    items = api("/v1/cases?status=all&limit=200", who)["items"]
    return next(c["id"] for c in items if c["patient"]["name"].startswith(patient_first_name))
