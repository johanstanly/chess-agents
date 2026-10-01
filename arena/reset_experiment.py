"""
Clean slate for a new version of the experiment.

  python arena/reset_experiment.py                      archives the old data as experiments/v1
  python arena/reset_experiment.py --archive v2         (a different archive name)

Shows exactly what it will do and asks "are you sure?" first. It MOVES (nothing is deleted):
  - every game on the website into experiments/<name>/games
    (the famous sample games go to tests/fixtures instead: the automatic checks use them)
  - Magnus's notebook, its dated copies, the lesson archive and the mistake library
  - the results table, the puzzle-test answers, the old experiment settings,
    the Claude usage log and the progress printouts
Then it locks the new experiment's settings in experiment.json.
experiments/ is not part of the website. All the code stays.

Options:  --model opus  --effort max   (the settings to lock)
"""

import argparse
import json
import shutil
import sys
from pathlib import Path

import diary
import experiment
import puzzles
from notebook import NOTEBOOK_DIR

ROOT = Path(__file__).resolve().parent.parent
LOGS_DIR = ROOT / "logs"
LIVE_STATUS = ROOT / "docs" / "live" / "status.json"


def planned_moves(archive: Path) -> list[tuple[Path, Path]]:
    """(from, to) for every file to move."""
    moves = []
    for path in sorted(diary.GAMES_DIR.glob("*.json")):
        if path.name == "index.json":
            continue
        sample = json.loads(path.read_text(encoding="utf-8")).get("kind") == "sample"
        moves.append((path, (diary.FIXTURES_DIR if sample else archive / "games") / path.name))
    notebook_files = [NOTEBOOK_DIR / n for n in ("magnus_notebook.md", "archive.jsonl", "mistakes.jsonl")]
    notebook_files += sorted((NOTEBOOK_DIR / "history").glob("*.md"))
    for path in notebook_files:
        if path.exists():
            moves.append((path, archive / path.relative_to(ROOT)))
    data = [experiment.RESULTS_FILE, experiment.SETTINGS_FILE, *sorted(puzzles.RESULTS_DIR.glob("puzzles-*.json"))]
    data += sorted(LOGS_DIR.glob("*.jsonl")) + sorted(LOGS_DIR.glob("*.txt"))
    for path in data:
        if path.exists():
            moves.append((path, archive / path.relative_to(ROOT)))
    return moves


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    parser = argparse.ArgumentParser(description="Clean slate and settings lock for the experiment.")
    parser.add_argument("--archive", default="v1", help="name of the folder in experiments/ for the old data")
    parser.add_argument("--model", default="opus",
                        help="the model; a shortcut like 'opus' is pinned to its exact model after the first request")
    parser.add_argument("--effort", default="max", choices=["low", "medium", "high", "xhigh", "max"])
    args = parser.parse_args()

    archive = ROOT / "experiments" / args.archive
    if archive.exists():
        print(f"Stopped: {archive.relative_to(ROOT)} already exists. Choose another name with --archive.")
        return 1
    if not puzzles.load_set():
        print("Stopped: there is no puzzle set yet. Make it first:   python arena/puzzles.py build")
        return 1
    moves = planned_moves(archive)
    print("This starts a new experiment from a clean slate. Nothing is deleted:\n")
    for source, target in moves:
        print(f"   {source.relative_to(ROOT)}  ->  {target.relative_to(ROOT)}")
    if not moves:
        print("   (nothing to move)")
    print(f"\nThen these settings are locked for all {len(experiment.schedule())} steps:")
    for key, value in experiment.current_settings(args.model, args.effort).items():
        print(f"   {key}: {value}")
    if input("\nType YES to go ahead (anything else cancels): ").strip() != "YES":
        print("Cancelled. Nothing was changed.")
        return 1

    for source, target in moves:
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.move(str(source), str(target))
    LIVE_STATUS.unlink(missing_ok=True)   # only meaningful while a game runs
    diary.rebuild_index()
    experiment.lock(args.model, args.effort)
    print(f"\nDone. {len(moves)} files moved; the old data is in {archive.relative_to(ROOT)}.")
    print("Settings locked in experiment.json. Start the experiment with:   python arena/play.py experiment")
    return 0


if __name__ == "__main__":
    sys.exit(main())
