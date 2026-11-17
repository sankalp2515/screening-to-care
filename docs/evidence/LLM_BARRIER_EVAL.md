# LLM barrier classifier vs keyword baseline

Run: `python -m tasleem.bench.llm_barriers --provider groq` with model `groq:openai/gpt-oss-120b` (17 Nov 2026). Synthetic messages only.
Keyword: **13/15**. LLM: **14/15** (0 calls failed or refused). Verdict: **switch on**.

| Message | Expected | Keyword | LLM |
|---|---|---|---|
| I am really scared of the camera test | FEAR | FEAR | FEAR |
| والله خايف من المنظار | FEAR | FEAR | FEAR |
| I don't understand what to drink the night before | PREP_UNCLEAR | PREP_UNCLEAR | PREP_UNCLEAR |
| وش اسوي في التحضير؟ ما فهمت | PREP_UNCLEAR | PREP_UNCLEAR | PREP_UNCLEAR |
| Nobody can take me home after the sedation | NO_ESCORT | NO_ESCORT | NO_ESCORT |
| ما في احد يوصلني | NO_ESCORT | NO_ESCORT | NO_ESCORT |
| I can't get a taxi that early | TRANSPORT | TRANSPORT | TRANSPORT |
| Is this covered by my insurance? | COST_OR_INSURANCE | COST_OR_INSURANCE | COST_OR_INSURANCE |
| My manager won't give me the day off | TIME_OR_WORK | none | TIME_OR_WORK |
| I need an Urdu interpreter | LANGUAGE | LANGUAGE | LANGUAGE |
| Can someone call me please | WANTS_CALLBACK | WANTS_CALLBACK | WANTS_CALLBACK |
| I did it in India last month | DONE_ELSEWHERE | none | DONE_ELSEWHERE |
| ok thanks | none | none | none |
| I'll think about it | none | none | none |
| My kids are sick this week | none | none | TIME_OR_WORK |

## How to read this

- **Too small to prove a difference.** 15 labelled messages; the LLM is ahead by one. With this few cases a one-message gap can be chance. Treat it as "no worse than keywords", not "better".
- **Where they differ.** The LLM caught two barriers the keyword rules missed ("manager won't give me the day off", "did it in India"). It also flagged one message with no barrier ("my kids are sick this week") as TIME_OR_WORK. That is a false barrier, but a plausible one.
- **What switching on means.** The model's code is shown as an "AI suggestion" that a navigator confirms or changes (rule R5). It never sets priority, closes a case or sends anything by itself. Distress detection stays on fixed rules and never depends on a model.
- **Data.** Synthetic messages only, sent to Groq's free tier on 17 Nov 2026. A production deployment would need a contracted model host in a UAE region, and the evaluation must be rerun on that model.
- **Next.** Grow the labelled set (more Arabic, Gulf dialect and Urdu messages) before relying on the result; the run is one command and takes about a minute.

