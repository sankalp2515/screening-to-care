"""UAE federal public holidays (TSL-164), used by working-day measures such as the national guideline's
"colonoscopy within 31 working days of referral".

Islamic holidays follow the moon sighting, so the dates below are the expected (astronomical) dates. The
programme replaces them with the official UAE Cabinet announcement each year; nothing else needs to change.
The weekend is Saturday and Sunday (UAE federal working week since January 2022).
"""

from __future__ import annotations

from datetime import date

UAE_PUBLIC_HOLIDAYS: frozenset[date] = frozenset({
    # 2026
    date(2026, 1, 1),                                        # New Year's Day
    date(2026, 3, 19), date(2026, 3, 20), date(2026, 3, 21),  # Eid al-Fitr (expected)
    date(2026, 5, 26),                                       # Arafat Day (expected)
    date(2026, 5, 27), date(2026, 5, 28), date(2026, 5, 29),  # Eid al-Adha (expected)
    date(2026, 6, 16),                                       # Islamic New Year (expected)
    date(2026, 8, 25),                                       # Prophet's Birthday (expected)
    date(2026, 12, 1),                                       # Commemoration Day
    date(2026, 12, 2), date(2026, 12, 3),                    # National Day
    # 2027
    date(2027, 1, 1),                                        # New Year's Day
    date(2027, 3, 9), date(2027, 3, 10), date(2027, 3, 11),   # Eid al-Fitr (expected)
    date(2027, 5, 15),                                       # Arafat Day (expected)
    date(2027, 5, 16), date(2027, 5, 17), date(2027, 5, 18),  # Eid al-Adha (expected)
    date(2027, 6, 6),                                        # Islamic New Year (expected)
    date(2027, 8, 14),                                       # Prophet's Birthday (expected)
    date(2027, 12, 1),                                       # Commemoration Day
    date(2027, 12, 2), date(2027, 12, 3),                    # National Day
})
