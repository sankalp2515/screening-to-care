"""Check the form text against its character limits: python docs/submission/count.py"""

import re
import sys
from pathlib import Path

LIMITS = {"summary": 2000, "built": 1500}
text = Path(__file__).with_name("FORM_TEXT.md").read_text(encoding="utf-8")
ok = True
for name, limit in LIMITS.items():
    m = re.search(rf"<!-- {name}:start -->\n(.*?)\n<!-- {name}:end -->", text, re.S)
    n = len(m.group(1).strip()) if m else -1
    ok &= 0 < n <= limit
    print(f"{name}: {n} / {limit} {'ok' if 0 < n <= limit else 'OVER'}")
sys.exit(0 if ok else 1)
