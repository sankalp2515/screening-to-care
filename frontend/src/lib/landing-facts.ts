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
  tests: "233",
  hardCases: "64 of 67",
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
} as const;

/** Published literature used on the page. */
export const LIT = {
  martin: { url: "https://pmc.ncbi.nlm.nih.gov/articles/PMC5164844/", cite: "Martin et al., Am J Med 2017 (n = 1,267)" },
  forbes: { url: "https://www.sciencedirect.com/science/article/pii/S1542356520313781", cite: "Forbes et al., Clin Gastroenterol Hepatol 2021" },
  ciemins: { url: "https://jamanetwork.com/journals/jamanetworkopen/fullarticle/2816737", cite: "Ciemins et al., JAMA Netw Open 2024" },
} as const;
