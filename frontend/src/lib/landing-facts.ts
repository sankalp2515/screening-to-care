/**
 * Every number the landing page shows, with where it comes from. Change a number here only after
 * re-running the source; the page must never show a figure the repository cannot reproduce.
 */
export const REPO = "https://github.com/sankalp2515/screening-to-care";
export const EVIDENCE = `${REPO}/blob/main/docs/evidence`;

/** Three-arm benchmark, design mix (docs/evidence/benchmark.md, seed 2026). */
export const BENCH = {
  tasleemFlagged: "98.5%",
  statusFlagged: "70.1%",
  tasleemDays: "4",
  statusDays: "14.4",
  falseDoneStatus: "125",
  falseDoneTasleem: "0",
  tests: "279",
  hardCases: "72 of 75",
} as const;

/** Real-world-fit run, published failure mix (docs/evidence/REAL_WORLD_FIT.md, seed 2026). */
export const REAL = {
  n: "2,000",
  neverColonoscopyFlaggedTasleem: "100%",
  neverColonoscopyFlaggedStatus: "92.0%",
  medianDaysTasleem: "1.9",
  medianDaysStatus: "16.5",
  veryTightDays: "2.8",
  veryTightAlertsPer100: "725",
  veryTightFalseAlertPct: "99.9%",
  alertsPer100: "53.5",
  falseAlertPct: "0.2%",
  fpMinutesPerWeekMid: "3",
  // Headline numbers, the same as the submission deck (REAL_WORLD_FIT.md, table rows "All journeys needing
  // action, flagged" and "false done").
  actionFlaggedTasleem: "99.9%",
  actionFlaggedStatus: "81.8%",
  falseDoneStatus: "160",
  falseDoneTasleem: "0",
} as const;

/** Abu Dhabi baseline: SEHA ambulatory clinics, 2015-16 (Almansoori et al., BMC Cancer 2021). 933 positive
 * tests had no colonoscopy; among the 436 who had one, 11 had cancer. 933 x 11 / 436 = 23.5 expected cancers. */
export const SEHA = {
  followedUp: "30.5%",
  noColonoscopy: "933",
  missedGiVisitPct: "36%",
  expectedCancers: "About 24",
} as const;

/** Published literature used on the page. */
export const LIT = {
  seha: { url: "https://link.springer.com/article/10.1186/s12885-021-08623-9", cite: "Almansoori et al., BMC Cancer 2021 (SEHA clinics, Abu Dhabi)" },
  martin: { url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC5164844/", cite: "Martin et al., Am J Med 2017 (n = 1,267)" },
  forbes: { url: "https://www.sciencedirect.com/science/article/pii/S1542356520313781", cite: "Forbes et al., Clin Gastroenterol Hepatol 2021" },
  ciemins: { url: "https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2816737", cite: "Ciemins et al., JAMA Netw Open 2024" },
} as const;
