"""
Automatic check of the replay website in a hidden browser:
replay self-test, evaluation bar, and analysis mode (your own moves).

Run:  python tests/check_website.py
"""

import sys

from browser_harness import run_page


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    print("Opening the website in a hidden browser (takes about 30 seconds)...\n")
    result = run_page("/__tests/website_check.html", timeout=240)
    print(result)
    return 0 if result.endswith("ALL CHECKS PASSED") else 1


if __name__ == "__main__":
    sys.exit(main())
