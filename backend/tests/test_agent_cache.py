"""The AI helper's reply cache: one model call per case state, failures retried, rate limits skipped fast.

Free model tiers allow few calls a day (Groq free: 8,000 tokens a minute, 200,000 a day), and every open of
the Assistant tab asks for a brief and a patient draft. The cache keeps the demo on the model; it never
changes what is shown, because a cached reply passes the same validators as a fresh one.
"""

from __future__ import annotations

from conftest import as_
from test_agent import FakeLLM, _agent, _case, core  # noqa: F401  (core is a fixture)

from tasleem_agent.assist import Brief, Draft, Sentence
from tasleem_agent.providers import CachedProvider, OfflineProvider, with_cache

SARA = as_("coord-sara")


class Counting:
    """A model that counts calls and can be told to fail like a rate-limited host."""

    name = "counting"

    def __init__(self, replies=None) -> None:
        self.calls = 0
        self.last_status: int | None = 200
        self.replies = list(replies or [])

    def structured(self, system, user, schema):
        self.calls += 1
        r = self.replies.pop(0) if self.replies else Draft(text=f"reply to {user}")
        self.last_status = 429 if r == 429 else 200
        return None if r in (None, 429) else r


class Clock:
    def __init__(self) -> None:
        self.t = 1000.0

    def __call__(self) -> float:
        return self.t


def test_same_prompt_calls_the_model_once_and_returns_a_safe_copy():
    inner = Counting()
    c = CachedProvider(inner)
    a = c.structured("sys", "facts A", Draft)
    a.text = "edited by a caller"
    b = c.structured("sys", "facts A", Draft)
    assert inner.calls == 1 and b.text == "reply to facts A"
    assert c.stats() == {"entries": 1, "hits": 1, "model_calls": 1, "paused": False}


def test_a_changed_case_is_a_new_prompt_and_asks_again():
    inner = Counting()
    c = CachedProvider(inner)
    c.structured("sys", "facts A", Draft)
    c.structured("sys", "facts A + a new barrier", Draft)
    c.structured("sys", "facts A", Brief)  # same text, other schema: other key
    assert inner.calls == 3


def test_failures_are_not_cached():
    inner = Counting(replies=[None, Draft(text="ok")])
    c = CachedProvider(inner)
    assert c.structured("sys", "u", Draft) is None
    assert c.structured("sys", "u", Draft).text == "ok"
    assert inner.calls == 2


def test_after_a_rate_limit_templates_are_used_at_once_until_the_cooldown_ends():
    inner, clock = Counting(replies=[429]), Clock()
    c = CachedProvider(inner, cooldown=60, clock=clock)
    assert c.structured("sys", "u1", Draft) is None
    assert c.structured("sys", "u2", Draft) is None and inner.calls == 1  # skipped, no wait
    assert c.stats()["paused"] is True
    clock.t += 61
    assert c.structured("sys", "u2", Draft).text == "reply to u2" and inner.calls == 2


def test_cache_is_bounded():
    c = CachedProvider(Counting(), max_entries=2)
    for u in ("a", "b", "c"):
        c.structured("sys", u, Draft)
    assert c.stats()["entries"] == 2


def test_offline_templates_and_a_disabled_cache_are_not_wrapped():
    off = OfflineProvider()
    assert with_cache(off, 512, 60) is off
    inner = Counting()
    assert with_cache(inner, 0, 60) is inner
    assert isinstance(with_cache(inner, 512, 60), CachedProvider)


def test_opening_the_assistant_twice_costs_one_model_call_per_case_state(core):  # noqa: F811
    """Two opens of the same case: the brief and draft come from the cache. After the patient reports a
    barrier, the facts change, so the brief is generated again."""
    cid = _case(core, "p-yousef")
    case = core.get(f"/v1/cases/{cid}", headers=SARA).json()
    seq = case["timeline"][0]["seq"]
    inner = FakeLLM(brief=Brief(sentences=[Sentence(text="The case is open.", cites=[seq])]), draft="See you soon.")
    calls: list[str] = []
    real = inner.structured

    def spy(system, user, schema):
        calls.append(schema.__name__)
        return real(system, user, schema)

    inner.structured = spy  # type: ignore[method-assign]
    with _agent(core, CachedProvider(inner)) as a:
        first = a.get(f"/v1/cases/{cid}/assist", headers=SARA).json()
        second = a.get(f"/v1/cases/{cid}/assist", headers=SARA).json()
        assert first["act"]["brief"]["sentences"] == second["act"]["brief"]["sentences"]
        assert second["act"]["brief"]["source"] == "llm"  # still validated and labelled as AI
        assert calls.count("Brief") == 1
        r = core.post(f"/v1/cases/{cid}/barriers", headers=as_("p-yousef"),
                      json={"codes": ["TIME_OR_WORK"], "text": "I have a shift that day"})
        assert r.status_code == 200
        a.get(f"/v1/cases/{cid}/assist", headers=SARA)
        assert calls.count("Brief") == 2
        assert a.get("/healthz").json()["llm_cache"]["hits"] >= 2
