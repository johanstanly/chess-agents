"""
Clean slate for the real experiment (Phase 10). Everything played so far was testing.

  python arena/reset_experiment.py

Shows exactly what it will delete and asks "are you sure?" first. It removes:
  - every AI game from the website (the famous sample games stay)
  - Magnus's notebook, its dated copies and the lesson archive
  - the results table, the Claude usage log and the progress printouts
Then it locks the experiment's settings in experiment.json.
All the code stays, and GitHub's history still has the old data.

Options:  --model claude-sonnet-5  --effort low   (the settings to lock)
"""

import argparse
import json
import sys
from pathlib import Path

import diary
import experiment
from notebook import NOTEBOOK_DIR

ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "logs"
LIVE_STATUS = ROOT / "docs" / "live" / "status.json"


def files_to_delete() -> list[Path]:
    found = []
    for path in sorted(diary.GAMES_DIR.glob("*.json")):
        if path.name != "index.json" and json.loads(path.read_text(encoding="utf-8")).get("kind") != "sample":
            found.append(path)
    found += [p for p in [NOTEBOOK_DIR / "magnus_notebook.md", NOTEBOOK_DIR / "archive.jsonl"] if p.exists()]
    found += sorted((NOTEBOOK_DIR / "history").glob("*.md"))
    found += [p for p in [experiment.RESULTS_FILE, experiment.SETTINGS_FILE, LIVE_STATUS] if p.exists()]
    found += sorted(LOGS_DIR.glob("*.jsonl")) + sorted(LOGS_DIR.glob("*.txt"))
    return found


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Clean slate and settings lock for the experiment.")
    parser.add_argument("--model", default="claude-sonnet-5",
                        help="the exact model (not a shortcut like 'sonnet', which can change meaning)")
    parser.add_argument("--effort", default="low", choices=["low", "medium", "high"])
    args = parser.parse_args()

    doomed = files_to_delete()
    print("This starts the real experiment from a clean slate.\n")
    if doomed:
        print(f"These {len(doomed)} files will be DELETED:")
        for path in doomed:
            print(f"   {path.relative_to(ROOT)}")
    else:
        print("Nothing to delete.")
    print("\nKept: all the code, the famous sample games, and GitHub's history of everything.")
    print(f"Then these settings are locked for all {len(experiment.schedule())} games:")
    for key, value in experiment.current_settings(args.model, args.effort).items():
        print(f"   {key}: {value}")
    if input("\nType YES to go ahead (anything else cancels): ").strip() != "YES":
        print("Cancelled. Nothing was changed.")
        return 1

    for path in doomed:
        path.unlink()
    diary.rebuild_index()
    experiment.lock(args.model, args.effort)
    print(f"\nDone. {len(doomed)} files deleted; settings locked in experiment.json.")
    print("Start the experiment with:   python arena/play.py experiment")
    return 0


if __name__ == "__main__":
    sys.exit(main())
