"""
Automatic checks for the live page (docs/live.html), in a hidden browser.
No Claude requests: costs nothing.

1. Real-speed replay: a finished game is played through the live page; after
   every move, the 2D board and the little 3D board must match the diary.
2. Live mode: a short demo game (random moves, made-up thoughts) is played in
   the background, and the page must follow it as it happens: thinking,
   thoughts typed into bubbles, moves, the end of the game and its review.
   The demo game is deleted afterwards.

Run:  python tests/check_live.py
"""

import subprocess
import sys
from pathlib import Path

from browser_harness import games_with_fixtures, run_page

ROOT = Path(__file__).resolve().parent.parent
GAMES = ROOT / "docs" / "games"


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("1. Real-speed replay through the live page")
    with games_with_fixtures() as games:   # the replay check uses a test-only game
        first = run_page("/__tests/live_check.html", timeout=150, games_dir=games)
    print(first)

    print("\n2. Live mode: following a demo game while it is played")
    before = set(GAMES.glob("*.json"))
    demo = subprocess.Popen([sys.executable, str(ROOT / "arena" / "play.py"), "demo-live", "--limit", "8", "--no-pause"],
                            cwd=ROOT, stdout=subprocess.DEVNULL, stderr=subprocess.STDOUT)
    try:
        second = run_page("/__tests/live_mode_check.html", timeout=300)
    finally:
        demo.wait(timeout=120)
        for path in set(GAMES.glob("*.json")) - before:   # remove the demo game again
            path.unlink()
        sys.path.insert(0, str(ROOT / "arena"))
        import diary
        diary.rebuild_index()
    print(second)
    ok = first.endswith("ALL CHECKS PASSED") and second.endswith("ALL CHECKS PASSED")
    print(f"\n{'ALL CHECKS PASSED' if ok else 'SOME CHECKS FAILED'}")
    return 0 if ok else 1


if __name__ == "__main__":
    sys.exit(main())
