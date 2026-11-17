"""Evaluate an LLM barrier classifier against the keyword classifier on the labelled hard cases (TSL-110).

    python -m tasleem.bench.llm_barriers                          # Claude: ANTHROPIC_API_KEY
    python -m tasleem.bench.llm_barriers --provider groq          # free tier: GROQ_API_KEY
    python -m tasleem.bench.llm_barriers --provider gemini        # free tier: GEMINI_API_KEY
    python -m tasleem.bench.llm_barriers --provider nvidia        # free tier: NVIDIA_API_KEY
    python -m tasleem.bench.llm_barriers --provider groq --list-models   # free: which model ids exist

Keys are read from the shell, else from backend/.env (git- and docker-ignored). The run stops at the
first reply that means the setup is wrong (bad key, unknown model) and writes no result file.

Free tiers allow few requests per minute: --pace adds a pause between calls (default 2.5 s), and
429 replies are retried after the host's Retry-After. Inputs are the synthetic hard cases only.

Writes docs/evidence/LLM_BARRIER_EVAL.md. The rule from the PRD: the LLM adapter is switched on only if
it matches or beats the keyword baseline on this set; otherwise it stays off. This is a dev tool, so it
may import both case-core and the agent; runtime services never import each other.
"""

from __future__ import annotations

import argparse
import time
from datetime import UTC, datetime
from pathlib import Path

from ..domain.barriers import KeywordBarrierClassifier
from .hardcases import BARRIER_CASES

OUT = Path(__file__).resolve().parents[3] / "docs" / "evidence" / "LLM_BARRIER_EVAL.md"


def main(argv: list[str] | None = None) -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--provider", default="claude",
                    choices=["claude", "groq", "gemini", "nvidia", "openrouter", "openai_compat"])
    ap.add_argument("--model", default="", help="model id; empty uses the provider's default")
    ap.add_argument("--base-url", default="", help="only for --provider openai_compat")
    ap.add_argument("--pace", type=float, default=None, help="seconds between calls (free tiers: 2.5)")
    ap.add_argument("--list-models", action="store_true", help="print the host's model ids and exit (free)")
    args = ap.parse_args(argv)
    from tasleem_agent.classify import suggest_barrier
    from tasleem_agent.providers import CONFIG_ERRORS, ClaudeProvider, make_openai_compat

    if args.provider == "claude":
        llm = ClaudeProvider(model=args.model or "claude-opus-5-5", timeout=30.0)
        pace = args.pace or 0.0
    else:
        try:
            llm = make_openai_compat(args.provider, args.model, timeout=30.0, base_url=args.base_url)
        except ValueError as exc:
            hint = "put it in backend/.env or your shell, never in the repo"
            raise SystemExit(f"{args.provider}: {exc} ({hint})") from None
        pace = 2.5 if args.pace is None else args.pace
        if args.list_models:
            print("\n".join(llm.list_models()))
            return
    if args.list_models:
        raise SystemExit("--list-models works with the free-tier providers")
    kw = KeywordBarrierClassifier()
    rows, kw_ok, llm_ok, llm_failed = [], 0, 0, 0
    for i, (text, expected) in enumerate(BARRIER_CASES):
        if i and pace:
            time.sleep(pace)
        k = kw.classify(text)
        k_code = k.code.value if k else "none"
        s = suggest_barrier(text, llm)
        status = getattr(llm, "last_status", 200)
        if s is None and status in CONFIG_ERRORS:
            raise SystemExit(f"stopped after call {i + 1}: the host replied {status}, which means the key or the "
                             f"model id ({llm.name}) is wrong. Try --list-models. No result file written.")
        l_code = s.code if s else "error"
        llm_failed += s is None
        kw_ok += k_code == expected
        llm_ok += l_code == expected
        rows.append(f"| {text} | {expected} | {k_code} | {l_code} |")
    n = len(BARRIER_CASES)
    verdict = "switch on" if llm_ok >= kw_ok and llm_failed == 0 else "stays off"
    OUT.write_text("\n".join([
        "# LLM barrier classifier vs keyword baseline", "",
        f"Run: `python -m tasleem.bench.llm_barriers --provider {args.provider}` with model `{llm.name}` "
        f"({datetime.now(UTC):%d %b %Y}). Synthetic messages only.",
        f"Keyword: **{kw_ok}/{n}**. LLM: **{llm_ok}/{n}** ({llm_failed} calls failed or refused). "
        f"Verdict: **{verdict}**.", "",
        "| Message | Expected | Keyword | LLM |", "|---|---|---|---|", *rows, ""]), encoding="utf-8")
    print({"keyword": kw_ok, "llm": llm_ok, "total": n, "failed": llm_failed, "verdict": verdict})


if __name__ == "__main__":
    main()
