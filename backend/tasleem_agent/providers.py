"""LLM providers. Every call is optional: on any error, refusal, timeout or invalid output the caller
falls back to deterministic templates, so the agent works fully offline and never blocks care."""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import threading
import time
from collections import OrderedDict
from collections.abc import Callable
from pathlib import Path
from typing import Any, Protocol, TypeVar

import httpx
from pydantic import BaseModel, ValidationError

log = logging.getLogger("tasleem.agent")
T = TypeVar("T", bound=BaseModel)


class LLMProvider(Protocol):
    name: str

    def structured(self, system: str, user: str, schema: type[T]) -> T | None: ...


class OfflineProvider:
    """No model. Templates and extractive summaries only. The default, and what the tests run."""

    name = "offline-templates"

    def structured(self, system: str, user: str, schema: type[T]) -> T | None:
        return None


class ClaudeProvider:
    """Anthropic Messages API with structured output (validated against the Pydantic schema).

    Inputs are pseudonymised by the caller (no names, no ids beyond the case reference). Short drafting
    tasks run at low effort. Refusals and errors return None, never raise into the request.
    """

    def __init__(self, model: str = "claude-opus-5-5", timeout: float = 20.0, max_retries: int = 2,
                 effort: str = "low") -> None:
        import anthropic  # optional dependency: pip install .[agent]

        self._anthropic = anthropic
        self.client = anthropic.Anthropic(timeout=timeout, max_retries=max_retries)
        self.model = model
        self.effort = effort
        self.name = f"claude:{model}"

    def structured(self, system: str, user: str, schema: type[T]) -> T | None:
        a = self._anthropic
        try:
            resp = self.client.beta.messages.parse(
                model=self.model,
                max_tokens=4000,
                system=system,
                messages=[{"role": "user", "content": user}],
                output_format=schema,
                output_config={"effort": self.effort},
                # On a policy refusal the API retries on a fallback model inside the same call.
                betas=["server-side-fallback-2026-07-01"],
                extra_body={"fallbacks": "default"},
            )
        except a.RateLimitError:
            log.warning("LLM rate limited; using templates")
            return None
        except a.APIStatusError as exc:
            log.warning("LLM error %s; using templates", exc.status_code)
            return None
        except a.APIConnectionError:
            log.warning("LLM unreachable; using templates")
            return None
        if resp.stop_reason == "refusal":
            log.info("LLM refused (%s); using templates", getattr(resp.stop_details, "category", None))
            return None
        return resp.parsed_output


# Free-tier and other hosts that speak the OpenAI-style chat-completions protocol. Model names change
# often: the defaults are starting points, so check the provider's console and set AGENT_LLM_MODEL.
PRESETS: dict[str, dict[str, str]] = {
    "groq": {"base_url": "https://api.groq.com/openai/v1", "key_env": "GROQ_API_KEY",
             "model": "openai/gpt-oss-120b"},
    "gemini": {"base_url": "https://generativelanguage.googleapis.com/v1beta/openai", "key_env": "GEMINI_API_KEY",
               "model": "gemini-2.5-flash"},
    "nvidia": {"base_url": "https://integrate.api.nvidia.com/v1", "key_env": "NVIDIA_API_KEY",
               "model": "meta/llama-3.3-70b-instruct"},
    "openrouter": {"base_url": "https://openrouter.ai/api/v1", "key_env": "OPENROUTER_API_KEY",
                   "model": "meta-llama/llama-3.3-70b-instruct:free"},
    # Azure OpenAI v1 API: base URL https://<resource>.openai.azure.com/openai/v1, model = the deployment name.
    "azure_openai": {"base_url": "", "key_env": "AZURE_OPENAI_API_KEY", "model": "gpt-5-mini"},
    "openai_compat": {"base_url": "", "key_env": "AGENT_LLM_API_KEY", "model": ""},
}

# Reasoning models reject `temperature` and `max_tokens`; they take `max_completion_tokens` (which also
# covers their hidden reasoning) and `reasoning_effort` instead.
_REASONING_MODEL = re.compile(r"^(?:[\w.-]+/)?(?:gpt-5|o\d)", re.IGNORECASE)


def is_reasoning_model(model: str) -> bool:
    return bool(_REASONING_MODEL.match(model))

# Replies that mean the configuration is wrong (key, model name, URL), not a one-off failure.
CONFIG_ERRORS = frozenset({400, 401, 403, 404, 422})

_FENCE = re.compile(r"^```(?:json)?\s*|\s*```$", re.IGNORECASE)


def _extract_json(text: str) -> str:
    """Models without strict JSON mode sometimes wrap the object in a code fence or add a sentence."""
    t = _FENCE.sub("", text.strip())
    start, end = t.find("{"), t.rfind("}")
    return t[start:end + 1] if start != -1 and end > start else t


class OpenAICompatProvider:
    """Any chat-completions host: Groq, Google AI Studio (Gemini), NVIDIA API catalog, or a local server.

    Uses httpx (already a dependency), so no extra package is needed. The schema goes into the system
    prompt and JSON mode is requested; the reply is validated with Pydantic. A host that rejects JSON
    mode is retried once without it. Any failure (auth, rate limit after retries, timeout, invalid JSON,
    schema mismatch) returns None and the caller uses templates. The key is never logged.
    """

    def __init__(self, base_url: str, api_key: str, model: str, *, name: str = "openai_compat",
                 timeout: float = 20.0, max_retries: int = 2, max_wait: float = 20.0,
                 transport: httpx.BaseTransport | None = None,
                 sleep: Callable[[float], None] = time.sleep, reasoning_effort: str = "low") -> None:
        if not base_url or not api_key or not model:
            raise ValueError("base_url, api_key and model are all required")
        self.client = httpx.Client(base_url=base_url.rstrip("/"), timeout=timeout, transport=transport,
                                   headers={"Authorization": f"Bearer {api_key}"})
        self.model = model
        self.reasoning = is_reasoning_model(model)
        self.reasoning_effort = reasoning_effort
        self.max_retries = max_retries
        self.max_wait = max_wait
        self._sleep = sleep
        self._json_mode = True
        self.name = f"{name}:{model}"
        self.last_status: int | None = None  # HTTP status of the last call (None: network error)

    def list_models(self) -> list[str]:
        """Model ids the host offers to this key. Free: generates nothing."""
        r = self.client.get("/models")
        r.raise_for_status()
        data = r.json()
        items = data.get("data", data) if isinstance(data, dict) else data
        return sorted(str(m.get("id")) for m in items if isinstance(m, dict) and m.get("id"))

    def _post(self, body: dict[str, Any]) -> httpx.Response | None:
        for attempt in range(self.max_retries + 1):
            try:
                r = self.client.post("/chat/completions", json=body)
            except httpx.HTTPError as exc:
                log.warning("LLM unreachable (%s); using templates", type(exc).__name__)
                return None
            if r.status_code in (429, 500, 502, 503, 504) and attempt < self.max_retries:
                try:
                    wait = float(r.headers.get("retry-after", ""))
                except ValueError:
                    wait = 2.0 * (attempt + 1)
                self._sleep(min(max(wait, 0.5), self.max_wait))
                continue
            return r
        return None

    def structured(self, system: str, user: str, schema: type[T]) -> T | None:
        sys_prompt = (f"{system}\n\nReply with one JSON object only, no prose, matching this JSON Schema:\n"
                      f"{json.dumps(schema.model_json_schema())}")
        body: dict[str, Any] = {"model": self.model,
                                "messages": [{"role": "system", "content": sys_prompt},
                                             {"role": "user", "content": user}]}
        if self.reasoning:
            body["max_completion_tokens"] = 6000
            if self.reasoning_effort:
                body["reasoning_effort"] = self.reasoning_effort
        else:
            body["temperature"] = 0
            body["max_tokens"] = 2000
        if self._json_mode:
            body["response_format"] = {"type": "json_object"}
        r = self._post(body)
        if r is not None and r.status_code == 400 and self._json_mode:
            # Some hosts or models do not support JSON mode: remember that and ask once without it.
            self._json_mode = False
            body.pop("response_format", None)
            r = self._post(body)
        self.last_status = r.status_code if r is not None else None
        if r is None:
            return None
        if r.status_code != 200:
            log.warning("LLM error %s; using templates", r.status_code)
            return None
        try:
            choice = r.json()["choices"][0]
            content = choice["message"].get("content") or ""
        except (ValueError, KeyError, IndexError, TypeError, AttributeError):
            log.warning("LLM reply had no message; using templates")
            return None
        if choice.get("finish_reason") == "content_filter" or not content.strip():
            log.info("LLM refused or returned nothing; using templates")
            return None
        try:
            return schema.model_validate_json(_extract_json(content))
        except ValidationError:
            log.warning("LLM reply did not match the schema; using templates")
            return None


class CachedProvider:
    """Remembers each successful model reply, so one case state costs one model call however often it is viewed.

    Every prompt is built only from the case's recorded facts or an approved template, so the key changes
    exactly when the case changes; a cached reply is never stale. Failures are not cached, so the next view
    tries again. After a rate-limit reply (HTTP 429) the model is skipped for `cooldown` seconds and the
    caller uses templates at once instead of waiting. Memory only, bounded, gone on restart: nothing is
    written to disk. A cached reply still goes through the same validators as a fresh one.
    """

    def __init__(self, inner: LLMProvider, max_entries: int = 512, cooldown: float = 60.0,
                 clock: Callable[[], float] = time.monotonic) -> None:
        self.inner = inner
        self.name = inner.name
        self.max_entries = max_entries
        self.cooldown = cooldown
        self._clock = clock
        self._cache: OrderedDict[str, BaseModel] = OrderedDict()
        self._lock = threading.Lock()
        self._paused_until = 0.0
        self.hits = 0
        self.calls = 0

    @staticmethod
    def _key(system: str, user: str, schema: type[BaseModel]) -> str:
        return hashlib.sha256(f"{schema.__name__}\0{system}\0{user}".encode()).hexdigest()

    def structured(self, system: str, user: str, schema: type[T]) -> T | None:
        key = self._key(system, user, schema)
        with self._lock:
            hit = self._cache.get(key)
            if hit is not None:
                self._cache.move_to_end(key)
                self.hits += 1
                return hit.model_copy(deep=True)  # type: ignore[return-value]
            if self._clock() < self._paused_until:
                return None
            self.calls += 1
        out = self.inner.structured(system, user, schema)
        with self._lock:
            if out is None:
                if getattr(self.inner, "last_status", None) == 429:
                    self._paused_until = self._clock() + self.cooldown
                    log.warning("LLM rate limited; templates for the next %.0f s", self.cooldown)
                return None
            self._cache[key] = out.model_copy(deep=True)
            while len(self._cache) > self.max_entries:
                self._cache.popitem(last=False)
        return out

    def stats(self) -> dict[str, Any]:
        with self._lock:
            return {"entries": len(self._cache), "hits": self.hits, "model_calls": self.calls,
                    "paused": self._clock() < self._paused_until}


def with_cache(llm: LLMProvider, max_entries: int, cooldown: float) -> LLMProvider:
    """Wrap a real model in the cache. Offline templates and a disabled cache (0 entries) pass through."""
    if isinstance(llm, OfflineProvider) or max_entries <= 0:
        return llm
    return CachedProvider(llm, max_entries=max_entries, cooldown=cooldown)


def _env(name: str, dotenv: str | Path = ".env") -> str:
    """A key from the environment, else from a local .env file (git- and docker-ignored)."""
    if os.environ.get(name):
        return os.environ[name]
    try:
        lines = Path(dotenv).read_text(encoding="utf-8").splitlines()
    except OSError:
        return ""
    for line in lines:
        k, sep, v = line.strip().partition("=")
        if sep and k.strip() == name and not k.strip().startswith("#"):
            return v.strip().strip("\"'")
    return ""


def make_openai_compat(kind: str, model: str = "", timeout: float = 20.0, base_url: str = "",
                       api_key: str = "", reasoning_effort: str = "low") -> OpenAICompatProvider:
    preset = PRESETS[kind]
    key = api_key or _env(preset["key_env"]) or _env("AGENT_LLM_API_KEY")
    if not key:
        raise ValueError(f"no API key: set {preset['key_env']}")
    return OpenAICompatProvider(base_url or preset["base_url"], key, model or preset["model"], name=kind,
                                timeout=timeout, reasoning_effort=reasoning_effort)


def make_provider(kind: str, model: str, timeout: float, *, base_url: str = "",
                  api_key: str = "", reasoning_effort: str = "low") -> LLMProvider:
    """Build the configured provider. A misconfigured model provider never stops the agent: it logs the
    reason and runs on templates."""
    try:
        if kind == "claude":
            return ClaudeProvider(model=model or "claude-opus-5-5", timeout=timeout)
        if kind in PRESETS:
            return make_openai_compat(kind, model, timeout, base_url, api_key, reasoning_effort)
    except (ImportError, ValueError) as exc:
        log.warning("LLM provider %s not available (%s); using templates", kind, exc)
    return OfflineProvider()
