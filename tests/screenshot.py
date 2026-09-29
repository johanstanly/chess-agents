"""
Takes a picture of the replay page, for checking how it looks.

Run:  python tests/screenshot.py OUTPUT.png [game-id] [half-move] [width,height]
"""

import sys

from browser_harness import run_page

out = sys.argv[1]
query = []
if len(sys.argv) > 2:
    query.append(f"game={sys.argv[2]}")
if len(sys.argv) > 3:
    query.append(f"move={sys.argv[3]}")
size = sys.argv[4] if len(sys.argv) > 4 else "1366,768"
print(run_page("/__tests/shot.html?" + "&".join(query), screenshot=out, size=size))
