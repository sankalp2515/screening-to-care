"""Evidence Reader evaluation: 20 labelled synthetic colonoscopy reports (17 English, 3 Arabic).

Run: python -m tasleem.bench.report_eval
Each label is what a gastroenterologist would take from the report; None means the report does not say.
The reports are invented and written in the styles seen in published report templates (no real patient text).
"""

from __future__ import annotations

import sys

from tasleem.domain.report_reader import FIELDS, read_report

T, F = True, False

# (report text, {field: expected}) - next_step is scored on presence (a quoted recommendation or None).
REPORTS: list[tuple[str, dict[str, object]]] = [
    ("Indication: positive FIT. Caecum reached and identified by appendiceal orifice. "
     "Bowel preparation BBPS 8 (3-3-2). "
     "Two polyps removed by cold snare, 4 mm and 6 mm. Histology pending. Repeat colonoscopy in 3 years if adenomas.",
     dict(completed=T, prep_adequate=T, polyps_removed=2, pathology_pending=T, next_step=T, follow_up="3 years")),
    ("Positive FIT. Incomplete colonoscopy: unable to advance beyond the hepatic flexure "
     "due to inadequate preparation. "
     "BBPS 1-1-0. No polyps seen in examined segments. Recommend repeat colonoscopy with extended prep in 3 months.",
     dict(completed=F, prep_adequate=F, polyps_removed=0, pathology_pending=F, next_step=T, follow_up="3 months")),
    ("Complete colonoscopy to the terminal ileum. Excellent preparation. No polyps. "
     "Return to routine screening in 10 years.",
     dict(completed=T, prep_adequate=T, polyps_removed=0, pathology_pending=F, next_step=T, follow_up="10 years")),
    ("The caecum was intubated. Preparation was fair with residual stool, Boston score 5. "
     "One 8 mm sessile polyp in the sigmoid, removed by snare polypectomy. Specimens sent to pathology. "
     "Plan: repeat colonoscopy in 1 year because of suboptimal prep.",
     dict(completed=T, prep_adequate=F, polyps_removed=1, pathology_pending=T, next_step=T, follow_up="1 year")),
    ("Procedure terminated at the splenic flexure because of patient discomfort. Prep good. "
     "Recommend CT colonography to complete the examination.",
     dict(completed=F, prep_adequate=T, polyps_removed=None, pathology_pending=None, next_step=T, follow_up=None)),
    ("Caecal intubation achieved. BBPS 9 (3-3-3). Three polyps removed, largest 12 mm. "
     "Histopathology: tubular adenoma with low-grade dysplasia. Surveillance colonoscopy in 3 years.",
     dict(completed=T, prep_adequate=T, polyps_removed=3, pathology_pending=F, next_step=T, follow_up="3 years")),
    ("Colonoscopy to caecum. Bowel prep adequate, BBPS 6 (2-2-2). No polyps or masses. "
     "Normal colonoscopy. Next screening colonoscopy in 10 years.",
     dict(completed=T, prep_adequate=T, polyps_removed=0, pathology_pending=F, next_step=T, follow_up="10 years")),
    ("Caecum not reached due to a fixed angulated sigmoid. Preparation satisfactory. Refer for CT colonography.",
     dict(completed=F, prep_adequate=T, polyps_removed=None, pathology_pending=None, next_step=T, follow_up=None)),
    ("The terminal ileum was intubated. Boston bowel preparation scale 2-2-1. A single 5 mm polyp was removed. "
     "Biopsies awaited. Follow-up to be decided after histology.",
     dict(completed=T, prep_adequate=F, polyps_removed=1, pathology_pending=T, next_step=T, follow_up=None)),
    ("Complete examination. Good bowel cleansing. Mass at 20 cm, biopsied and tattooed. Histology pending. "
     "Urgent referral to colorectal surgery.",
     dict(completed=T, prep_adequate=T, polyps_removed=None, pathology_pending=T, next_step=T, follow_up=None)),
    ("Ileocaecal valve visualised. Poor preparation in the right colon. No polyps seen. "
     "Repeat in 6 months with split-dose prep.",
     dict(completed=T, prep_adequate=F, polyps_removed=0, pathology_pending=F, next_step=T, follow_up="6 months")),
    ("Caecum reached. BBPS 7 (2-3-2). Four polyps removed by cold snare. Pathology: hyperplastic polyps, no dysplasia. "
     "Repeat colonoscopy in 5 years.",
     dict(completed=T, prep_adequate=T, polyps_removed=4, pathology_pending=F, next_step=T, follow_up="5 years")),
    ("Failed to intubate the caecum; looping in the transverse colon. Preparation excellent. "
     "Recommend repeat with a paediatric colonoscope within 6 weeks.",
     dict(completed=F, prep_adequate=T, polyps_removed=None, pathology_pending=None, next_step=T, follow_up="6 weeks")),
    ("Complete colonoscopy to the caecum. Adequate prep. Two diminutive polyps resected and retrieved. "
     "Awaiting histology before setting the surveillance interval.",
     dict(completed=T, prep_adequate=T, polyps_removed=2, pathology_pending=T, next_step=T, follow_up=None)),
    ("Appendiceal orifice seen. Prep suboptimal, BBPS 4. No polyps in the visualised mucosa. "
     "Repeat colonoscopy in 1 year.",
     dict(completed=T, prep_adequate=F, polyps_removed=0, pathology_pending=F, next_step=T, follow_up="1 year")),
    ("Caecum reached and photographed. Excellent preparation, BBPS 9. Multiple polyps removed by snare. "
     "Specimens submitted for histology. Discuss at MDT; repeat colonoscopy in 1 year.",
     dict(completed=T, prep_adequate=T, polyps_removed=2, pathology_pending=T, next_step=T, follow_up="1 year")),
    ("Incomplete study, stopped at the descending colon due to solid stool. Inadequate preparation. "
     "Rebook with 2-day prep.",
     dict(completed=F, prep_adequate=F, polyps_removed=None, pathology_pending=None, next_step=T, follow_up=None)),
    ("تم الوصول إلى الأعور. تحضير جيد. لا توجد زوائد. يوصى بإعادة المنظار بعد عشر سنوات.",
     dict(completed=T, prep_adequate=T, polyps_removed=0, pathology_pending=F, next_step=T, follow_up="10 years")),
    ("منظار غير مكتمل بسبب تحضير ضعيف. يوصى بإعادة المنظار خلال ثلاثة أشهر.",
     dict(completed=F, prep_adequate=F, polyps_removed=None, pathology_pending=None,
          next_step=T, follow_up="3 months")),
    ("تم الوصول إلى الأعور. تحضير جيد. تم استئصال زائدة واحدة. نتيجة الخزعة قيد الانتظار.",
     dict(completed=T, prep_adequate=T, polyps_removed=1, pathology_pending=T, next_step=None, follow_up=None)),
]


# Held out: written after the reader was finished and never used to tune it. Misses here are reported, not fixed.
HELD_OUT: list[tuple[str, dict[str, object]]] = [
    ("Scope advanced to the caecum with ease. Cleansing was good throughout. A 3 mm polyp in the rectum was removed. "
     "Histology to follow. Repeat in 5 years if benign.",
     dict(completed=T, prep_adequate=T, polyps_removed=1, pathology_pending=T, next_step=T, follow_up="5 years")),
    ("Examination limited to the sigmoid colon because of a stricture. Biopsies taken. Pathology pending. "
     "Refer to surgeons urgently.",
     dict(completed=F, prep_adequate=None, polyps_removed=None, pathology_pending=T, next_step=T, follow_up=None)),
    ("Total colonoscopy performed. Boston score 3 (1-1-1), much residual fluid. No lesions seen. Re-scope in 3 months.",
     dict(completed=T, prep_adequate=F, polyps_removed=0, pathology_pending=F, next_step=T, follow_up="3 months")),
    ("Caecum and terminal ileum visualised. BBPS 8. Two adenomatous-looking polyps excised. Await pathology.",
     dict(completed=T, prep_adequate=T, polyps_removed=2, pathology_pending=T, next_step=None, follow_up=None)),
    ("Could not pass the scope beyond 40 cm. Preparation poor. Rebook with enhanced bowel preparation in 4 weeks.",
     dict(completed=F, prep_adequate=F, polyps_removed=None, pathology_pending=None, next_step=T, follow_up="4 weeks")),
    ("Full colonoscopy to the caecum. Very good prep. No polyps detected. Routine screening again in 10 years.",
     dict(completed=T, prep_adequate=T, polyps_removed=0, pathology_pending=F, next_step=T, follow_up="10 years")),
    ("Caecum reached. Prep adequate. Five polyps removed, two over 10 mm. Histology: two tubulovillous adenomas. "
     "Surveillance in 1 year.",
     dict(completed=T, prep_adequate=T, polyps_removed=5, pathology_pending=F, next_step=T, follow_up="1 year")),
    ("تم الوصول إلى الأعور. تحضير ضعيف. يوصى بإعادة المنظار بعد ستة أشهر.",
     dict(completed=T, prep_adequate=F, polyps_removed=None, pathology_pending=None,
          next_step=T, follow_up="6 months")),
]


def score_field(field: str, got: object, want: object) -> bool:
    if field == "next_step":
        return (got is not None) == bool(want)
    return got == want


def evaluate(reports: list[tuple[str, dict[str, object]]] | None = None) -> tuple[float, list[str]]:
    total = right = 0
    misses: list[str] = []
    for i, (text, labels) in enumerate(REPORTS if reports is None else reports, 1):
        reading = read_report(text)
        for field in FIELDS:
            total += 1
            got = reading[field].value
            if score_field(field, got, labels[field]):
                right += 1
            else:
                misses.append(f"R{i:02d} {field}: expected {labels[field]!r}, read {got!r}")
    return right / total, misses


def evaluate_model(reports: list[tuple[str, dict[str, object]]]) -> tuple[float, int, list[str], str]:
    """Score the agent's model reader, configured exactly as the deployed agent (AGENT_* settings).
    Returns accuracy, wrong-value count (a stated value that is wrong, the dangerous kind), misses, model name."""
    from tasleem_agent.app import get_settings
    from tasleem_agent.providers import make_provider
    from tasleem_agent.report_reading import read_with_model

    st = get_settings()
    llm = make_provider(st.llm_provider, st.llm_model, 60.0, base_url=st.llm_base_url,
                        api_key=st.llm_api_key.get_secret_value(), reasoning_effort=st.llm_reasoning_effort)
    total = right = wrong = failed = 0
    misses: list[str] = []
    for i, (text, labels) in enumerate(reports, 1):
        out = read_with_model(text, llm)
        if out is None:  # the product falls back to the keyword reader here; scored as blanks, the strict view
            failed += 1
            out = {"fields": {f: {"value": None} for f in FIELDS}}
            misses.append(f"R{i:02d} no valid model answer (product shows the keyword reading)")
        for field in FIELDS:
            total += 1
            got = out["fields"][field]["value"]
            if score_field(field, got, labels[field]):
                right += 1
            else:
                wrong += got is not None and field != "next_step"
                misses.append(f"R{i:02d} {field}: expected {labels[field]!r}, read {got!r}")
    if failed == len(reports):
        raise SystemExit(f"{llm.name}: no answers at all; check the agent's model settings")
    return right / total, wrong, misses, llm.name


def main() -> int:
    if "--model" in sys.argv:
        acc, wrong, misses, name = evaluate_model(REPORTS + HELD_OUT)
        print(f"Evidence Reader (model {name}): {acc:.1%} field accuracy on {len(REPORTS) + len(HELD_OUT)} "
              f"reports; {wrong} stated values wrong")
        for m in misses:
            print("  miss:", m)
        return 0
    acc, misses = evaluate()
    print(f"Evidence Reader (keyword fallback): {acc:.1%} field accuracy on {len(REPORTS)} reports, "
          f"{len(REPORTS) * len(FIELDS)} fields")
    for m in misses:
        print("  miss:", m)
    held, held_misses = evaluate(HELD_OUT)
    print(f"Held out: {held:.1%} on {len(HELD_OUT)} reports written after the reader was frozen")
    for m in held_misses:
        print("  miss:", m)
    return 0 if acc >= 0.9 else 1


if __name__ == "__main__":
    sys.exit(main())
