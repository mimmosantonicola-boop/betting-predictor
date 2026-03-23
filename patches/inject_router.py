"""
inject_router.py — Adds the BettingView route to MiroFish's Vue Router.
Run after copying BettingView.vue into the frontend.
"""

import re
import sys
from pathlib import Path

ROUTER_PATH = Path("mirofish/frontend/src/router/index.js")

IMPORT_LINE = "import BettingView from '../views/BettingView.vue'"
ROUTE_BLOCK = """\
  {
    path: '/betting',
    name: 'betting',
    component: BettingView,
  },"""

NAV_LINK = ""  # Not injecting nav link here — BettingView has its own header


def inject():
    if not ROUTER_PATH.exists():
        print(f"[WARN] Router file not found at {ROUTER_PATH}")
        print("       You may need to add the Betting route manually.")
        return

    text = ROUTER_PATH.read_text(encoding="utf-8")

    # Add import if not present
    if "BettingView" not in text:
        # Insert after the last existing import
        last_import = max(
            (m.end() for m in re.finditer(r"^import .+$", text, re.MULTILINE)),
            default=0,
        )
        text = text[:last_import] + "\n" + IMPORT_LINE + text[last_import:]
        print("[OK] Added BettingView import to router")
    else:
        print("[SKIP] BettingView import already present")

    # Add route if not present
    if "path: '/betting'" not in text:
        # Insert before the closing of routes array
        routes_end = text.rfind("]")
        if routes_end == -1:
            print("[WARN] Could not find routes array end — add route manually")
        else:
            text = text[:routes_end] + ROUTE_BLOCK + "\n" + text[routes_end:]
            print("[OK] Added /betting route to router")
    else:
        print("[SKIP] /betting route already present")

    ROUTER_PATH.write_text(text, encoding="utf-8")
    print("[OK] Router patched successfully")
    print("     Navigate to http://localhost:3000/betting in your browser")


if __name__ == "__main__":
    inject()
