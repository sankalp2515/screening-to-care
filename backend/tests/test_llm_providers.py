"""OpenAI-compatible provider (Groq, Gemini, NVIDIA, any chat-completions host).

No network and no key: a fake transport plays the host. The point is that every failure mode falls
back to templates (None) and never raises into a request, and that a good reply is schema-validated.
"""

from __future__ import annotations

import json
import logging

import httpx
import pytest

from tasleem_agent.classify import BarrierSuggestion, suggest_barrier
from tasleem_agent.providers import (
    PRESETS,
    OfflineProvider,
    OpenAICompatProvider,
    _env,
    _extract_json,
    make_provider,
)

SECRET = "sk-test-not-a-real-key-123"


def _reply(content: str, finish: str = "stop") -> dict:
    return {"choices": [{"message": {"role": "assistant", "content": content}, "finish_reason": finish}]}


def _provider(handler, **kw) -> tuple[OpenAICompatProvider, list[httpx.Request], list[float]]:
    seen: list[httpx.Request] = []
    waits: list[float] = []

    def h(request: httpx.Request) -> httpx.Response:
        seen.append(request)
        return handler(request, len(seen))

    p = OpenAICompatProvider("https://llm.test/v1", SECRET, "test-model", transport=httpx.MockTransport(h),
                             sleep=waits.append, **kw)
    return p, seen, waits


def test_good_reply_is_validated_and_request_is_well_formed():
    p, seen, _ = _provider(lambda r, n: httpx.Response(200, json=_reply('{"code": "TRANSPORT", "confidence": 0.9}')))
    out = suggest_barrier("No bus to the hospital on Thursday", p)
    assert out == BarrierSuggestion(code="TRANSPORT", confidence=0.9)
    req = seen[0]
    assert str(req.url) == "https://llm.test/v1/chat/completions"
    assert req.headers["authorization"] == f"Bearer {SECRET}"
    body = json.loads(req.content)
    assert body["model"] == "test-model" and body["temperature"] == 0
    assert body["response_format"] == {"type": "json_object"}
    assert "JSON Schema" in body["messages"][0]["content"] and "TRANSPORT" in body["messages"][0]["content"]
    assert p.name == "openai_compat:test-model"


def test_fenced_json_with_prose_is_extracted():
    text = 'Sure! Here it is:\n```json\n{"code": "FEAR", "confidence": 0.7}\n```'
    p, _, _ = _provider(lambda r, n: httpx.Response(200, json=_reply(text)))
    assert suggest_barrier("I am scared", p).code == "FEAR"
    assert _extract_json("no json here") == "no json here"


@pytest.mark.parametrize("content", ['{"code": "MADE_UP", "confidence": 0.9}',
                                     '{"code": "FEAR", "confidence": 7}', "not json at all", ""])
def test_invalid_or_off_vocabulary_reply_falls_back(content):
    p, _, _ = _provider(lambda r, n: httpx.Response(200, json=_reply(content)))
    assert suggest_barrier("anything", p) is None


def test_content_filter_counts_as_refusal():
    filtered = _reply('{"code":"FEAR","confidence":1}', "content_filter")
    p, _, _ = _provider(lambda r, n: httpx.Response(200, json=filtered))
    assert suggest_barrier("anything", p) is None


def test_rate_limit_is_retried_after_retry_after_then_succeeds():
    def h(r, n):
        if n == 1:
            return httpx.Response(429, headers={"retry-after": "3"})
        return httpx.Response(200, json=_reply('{"code": "TIME_OR_WORK", "confidence": 0.8}'))

    p, seen, waits = _provider(h)
    assert suggest_barrier("cannot get leave from work", p).code == "TIME_OR_WORK"
    assert len(seen) == 2 and waits == [3.0]


def test_persistent_rate_limit_gives_up_with_capped_waits():
    p, seen, waits = _provider(lambda r, n: httpx.Response(429, headers={"retry-after": "999"}), max_retries=2)
    assert suggest_barrier("x", p) is None
    assert len(seen) == 3 and waits == [20.0, 20.0]


def test_host_without_json_mode_is_retried_once_without_it():
    def h(r, n):
        if "response_format" in json.loads(r.content):
            return httpx.Response(400, json={"error": {"message": "response_format not supported"}})
        return httpx.Response(200, json=_reply('{"code": "LANGUAGE", "confidence": 0.6}'))

    p, seen, _ = _provider(h)
    assert suggest_barrier("I need an interpreter", p).code == "LANGUAGE"
    assert len(seen) == 2
    suggest_barrier("again", p)  # remembered: no third failing JSON-mode call
    assert len(seen) == 3 and "response_format" not in json.loads(seen[2].content)


@pytest.mark.parametrize("status", [401, 403, 404, 500])
def test_auth_and_server_errors_fall_back_without_leaking_the_key(status, caplog):
    caplog.set_level(logging.DEBUG)
    p, _, _ = _provider(lambda r, n: httpx.Response(status, json={"error": "nope"}), max_retries=0)
    assert suggest_barrier("x", p) is None
    assert SECRET not in caplog.text


def test_network_error_falls_back():
    def h(r, n):
        raise httpx.ConnectError("down")

    p, _, _ = _provider(h)
    assert suggest_barrier("x", p) is None


def test_malformed_envelope_falls_back():
    p, _, _ = _provider(lambda r, n: httpx.Response(200, json={"unexpected": True}))
    assert suggest_barrier("x", p) is None


def test_presets_and_factory(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)  # never read the developer's real backend/.env
    assert set(PRESETS) == {"groq", "gemini", "nvidia", "openrouter", "azure_openai", "openai_compat"}
    for name in ("groq", "gemini", "nvidia", "openrouter"):
        assert PRESETS[name]["base_url"].startswith("https://")
    for env in ("GROQ_API_KEY", "GEMINI_API_KEY", "NVIDIA_API_KEY", "OPENROUTER_API_KEY", "AGENT_LLM_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    # No key: the agent still starts, on templates.
    assert isinstance(make_provider("groq", "", 5), OfflineProvider)
    assert isinstance(make_provider("openai_compat", "m", 5, base_url="https://x.test/v1"), OfflineProvider)
    monkeypatch.setenv("GROQ_API_KEY", SECRET)
    g = make_provider("groq", "", 5)
    assert isinstance(g, OpenAICompatProvider) and g.name == f"groq:{PRESETS['groq']['model']}"
    assert make_provider("gemini", "my-model", 5, api_key="k").name == "gemini:my-model"
    # openai_compat needs a base URL and a model.
    assert isinstance(make_provider("openai_compat", "", 5, api_key="k"), OfflineProvider)
    assert make_provider("openai_compat", "m", 5, base_url="https://x.test/v1", api_key="k").name == "openai_compat:m"
    assert isinstance(make_provider("offline", "", 5), OfflineProvider)


def test_last_status_and_list_models():
    def h(r, n):
        if r.url.path.endswith("/models"):
            return httpx.Response(200, json={"data": [{"id": "b-model"}, {"id": "a-model"}, {"x": 1}]})
        return httpx.Response(404, json={"error": "model not found"})

    p, _, _ = _provider(h, max_retries=0)
    assert p.list_models() == ["a-model", "b-model"]
    assert suggest_barrier("x", p) is None and p.last_status == 404


def test_eval_stops_on_a_config_error_and_writes_nothing(monkeypatch, tmp_path):
    from tasleem.bench import llm_barriers
    from tasleem_agent import providers

    out = tmp_path / "eval.md"
    monkeypatch.setattr(llm_barriers, "OUT", out)
    calls: list[int] = []

    def fake_factory(kind, model="", timeout=20.0, base_url="", api_key=""):
        def h(r):
            calls.append(1)
            return httpx.Response(404, json={"error": "model not found"})

        return OpenAICompatProvider("https://llm.test/v1", "k", "gone-model", transport=httpx.MockTransport(h),
                                    max_retries=0)

    monkeypatch.setattr(providers, "make_openai_compat", fake_factory)
    with pytest.raises(SystemExit, match="replied 404"):
        llm_barriers.main(["--provider", "groq", "--pace", "0"])
    assert len(calls) == 1 and not out.exists()


def test_agent_settings_read_provider_from_env(monkeypatch):
    from tasleem_agent.app import AgentSettings

    monkeypatch.setenv("AGENT_LLM_PROVIDER", "nvidia")
    monkeypatch.setenv("AGENT_LLM_API_KEY", SECRET)
    s = AgentSettings(_env_file=None)
    assert s.llm_provider == "nvidia" and s.llm_api_key.get_secret_value() == SECRET
    assert SECRET not in repr(s)


def test_key_is_read_from_a_dotenv_file(tmp_path, monkeypatch):
    monkeypatch.delenv("GROQ_API_KEY", raising=False)
    f = tmp_path / ".env"
    f.write_text('# GROQ_API_KEY=commented\nOTHER=1\nGROQ_API_KEY="from-file"\n', encoding="utf-8")
    assert _env("GROQ_API_KEY", f) == "from-file"
    assert _env("MISSING", f) == "" and _env("GROQ_API_KEY", tmp_path / "nope") == ""
    monkeypatch.setenv("GROQ_API_KEY", "from-shell")
    assert _env("GROQ_API_KEY", f) == "from-shell"


# --- Reasoning models (gpt-5 family on Azure OpenAI): different request parameters -------------------


@pytest.mark.parametrize("model,reasoning", [
    ("gpt-5-mini", True), ("GPT-5", True), ("openai/gpt-5-nano", True), ("o4-mini", True), ("o3", True),
    ("gpt-4o-mini", False), ("openai/gpt-oss-120b", False), ("meta/llama-3.3-70b-instruct", False),
    ("gemini-3.5-flash", False), ("", False),
])
def test_reasoning_models_are_recognised_by_name(model, reasoning):
    from tasleem_agent.providers import is_reasoning_model

    assert is_reasoning_model(model) is reasoning


def test_reasoning_model_request_drops_temperature_and_uses_completion_tokens():
    seen: list[httpx.Request] = []

    def h(r):
        seen.append(r)
        return httpx.Response(200, json=_reply('{"code": "COST_OR_INSURANCE", "confidence": 0.8}'))

    p = OpenAICompatProvider("https://res.openai.azure.com/openai/v1", SECRET, "gpt-5-mini", name="azure_openai",
                             transport=httpx.MockTransport(h), reasoning_effort="minimal")
    want = BarrierSuggestion(code="COST_OR_INSURANCE", confidence=0.8)
    assert suggest_barrier("I cannot afford the copay", p) == want
    body = json.loads(seen[0].content)
    assert "temperature" not in body and "max_tokens" not in body
    assert body["max_completion_tokens"] >= 2000 and body["reasoning_effort"] == "minimal"
    assert body["response_format"] == {"type": "json_object"}
    assert str(seen[0].url) == "https://res.openai.azure.com/openai/v1/chat/completions"
    assert p.name == "azure_openai:gpt-5-mini"


def test_non_reasoning_model_request_is_unchanged():
    p, seen, _ = _provider(lambda r, n: httpx.Response(200, json=_reply('{"code": "FEAR", "confidence": 0.6}')))
    suggest_barrier("I am scared of the test", p)
    body = json.loads(seen[0].content)
    assert body["temperature"] == 0 and body["max_tokens"] == 2000
    assert "reasoning_effort" not in body and "max_completion_tokens" not in body


def test_azure_openai_preset_needs_base_url_and_reads_its_own_key(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    for env in ("AZURE_OPENAI_API_KEY", "AGENT_LLM_API_KEY"):
        monkeypatch.delenv(env, raising=False)
    assert isinstance(make_provider("azure_openai", "", 5, base_url="https://r.openai.azure.com/openai/v1"),
                      OfflineProvider)  # no key: templates
    monkeypatch.setenv("AZURE_OPENAI_API_KEY", SECRET)
    assert isinstance(make_provider("azure_openai", "", 5), OfflineProvider)  # no base URL: templates
    p = make_provider("azure_openai", "", 5, base_url="https://r.openai.azure.com/openai/v1", reasoning_effort="low")
    assert isinstance(p, OpenAICompatProvider) and p.name == "azure_openai:gpt-5-mini"
    assert p.reasoning and p.reasoning_effort == "low"


def test_agent_settings_accept_azure_openai(monkeypatch):
    from tasleem_agent.app import AgentSettings

    monkeypatch.setenv("AGENT_LLM_PROVIDER", "azure_openai")
    monkeypatch.setenv("AGENT_LLM_REASONING_EFFORT", "minimal")
    s = AgentSettings(_env_file=None)
    assert s.llm_provider == "azure_openai" and s.llm_reasoning_effort == "minimal"


def test_agent_server_database_pool_heals_dropped_connections():
    # Live Azure finding (19 Nov): a pooled Postgres connection went idle during a model call and the draft
    # save failed with "SSL error: unexpected eof" (HTTP 500 on the Assistant tab).
    from tasleem_agent.app import POOL_RECYCLE_SECONDS, make_engine
    engine = make_engine("postgresql+psycopg://u:p@db.invalid:5432/agent")
    assert engine.pool._pre_ping is True
    assert engine.pool._recycle == POOL_RECYCLE_SECONDS < 240  # under Azure's 4-minute idle cut-off
    engine.dispose()


def test_notifier_server_database_pool_heals_dropped_connections():
    import tasleem_notifier.store as store
    seen: dict = {}
    real = store.create_engine
    store.create_engine = lambda url, **kw: (seen.update(kw), real("sqlite://"))[1]
    try:
        store.make_store("postgresql+psycopg://u:p@db.invalid:5432/notifier")
    finally:
        store.create_engine = real
    assert seen["pool_pre_ping"] is True and seen["pool_recycle"] < 240
    assert seen["connect_args"]["keepalives"] == 1
