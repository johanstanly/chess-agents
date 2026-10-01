"""
The experiment (version 2): its locked settings, its schedule and its results table.

Schedule:
  checkpoint 0    the puzzle test (Magnus, Hans), then each plays Stockfish twice
                  (once as White, once as Black)
  games 1-10      Magnus vs Hans, each from an opening of the book (openings.py);
                  after every game Magnus studies it and rewrites his notebook
  checkpoint 10   the puzzle test and the 4 Stockfish games again
  games 11-20     Magnus vs Hans
  checkpoint 20   the puzzle test and the 4 Stockfish games again

The settings are locked in experiment.json (written by reset_experiment.py) and
must not change until the experiment is over; otherwise later games could not be
compared with earlier ones. The prompts, the openings and the puzzle set are
locked by their fingerprints: if one is edited, the runner refuses to continue.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import notebook
import openings
import puzzles
import review

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = ROOT / "experiment.json"
RESULTS_FILE = ROOT / "docs" / "data" / "results.json"
PROMPTS_DIR = ROOT / "prompts"

VERSION = 2
MATCH_GAMES = 20
CHECKPOINTS = (0, 10, 20)               # tested before game 1, after game 10 and after game 20
YARDSTICK_SKILL = 0
YARDSTICK_THINK_SECONDS = 0.05


def fingerprint(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]


def prompt_fingerprints() -> dict:
    """A short fingerprint of every prompt file: it changes if even one letter changes
    (but not if only the line endings change, which Git may do on Windows)."""
    return {p.name: fingerprint(p.read_text(encoding="utf-8").replace("\r\n", "\n"))
            for p in sorted(PROMPTS_DIR.glob("*.txt"))}


def current_settings(model: str, effort: str) -> dict:
    """Everything that must stay the same for the whole experiment."""
    return {
        "version": VERSION,
        "model": model,
        "effort": effort,
        "match_games": MATCH_GAMES,
        "checkpoints": list(CHECKPOINTS),
        "yardstick_skill": YARDSTICK_SKILL,
        "yardstick_think_seconds": YARDSTICK_THINK_SECONDS,
        "review_depth": review.DEPTH,
        "notebook_cap": notebook.NOTEBOOK_CAP,
        "worst_moves": notebook.WORST_MOVES,
        "mistakes_shown": notebook.MISTAKES_SHOWN,
        "library_labels": list(notebook.LIBRARY_LABELS),
        "openings": fingerprint(json.dumps([openings.OPENINGS, openings.CHECKPOINT_OPENINGS])),
        "puzzle_set": puzzles.fingerprint(),
        "prompts": prompt_fingerprints(),
    }


def lock(model: str, effort: str) -> dict:
    settings = {"started": datetime.now().isoformat(timespec="seconds"), **current_settings(model, effort)}
    save_settings(settings)
    return settings


def save_settings(settings: dict) -> None:
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")


def load() -> dict | None:
    return json.loads(SETTINGS_FILE.read_text(encoding="utf-8")) if SETTINGS_FILE.exists() else None


def changes_since_lock(settings: dict) -> list[str]:
    """What differs from the locked settings (empty if nothing)."""
    now = current_settings(settings["model"], settings["effort"])
    return [f"{key}: locked {settings.get(key)!r}, now {value!r}"
            for key, value in now.items() if settings.get(key) != value]


def main_model(models: list[str], alias: str) -> str | None:
    """Which of the models in a Claude Code answer is the experiment's model
    (Claude Code also uses a small helper model for itself)."""
    matches = [m for m in models if alias in m]
    return matches[0] if len(matches) == 1 else None


# ---------- The schedule ----------

def schedule() -> list[dict]:
    """Every step of the experiment, in order. For games, "key" is the end of the game's id."""
    steps = []

    def checkpoint(n: int) -> None:
        for agent in ("magnus", "hans"):
            steps.append({"key": f"puzzles-{n:02d}-{agent}", "kind": "puzzles", "checkpoint": n, "agent": agent})
        for agent in ("magnus", "hans"):
            for color in ("white", "black"):
                steps.append({"key": f"checkpoint-{n:02d}-{agent}-{color}", "kind": "yardstick",
                              "checkpoint": n, "agent": agent, "color": color,
                              "opening": openings.CHECKPOINT_OPENINGS[color]})

    for number in range(MATCH_GAMES + 1):
        if number in CHECKPOINTS:
            checkpoint(number)
        if number < MATCH_GAMES:
            n = number + 1
            steps.append({"key": f"match-{n:02d}", "kind": "match", "number": n,
                          "magnus_white": n % 2 == 1,   # Magnus is White in odd games
                          "opening": openings.for_match_game(n)["name"]})
    return steps


def find_game(step: dict, games: list[dict]) -> dict | None:
    if step["kind"] == "puzzles":
        return None
    return next((d for d in games if d["id"].endswith("-" + step["key"])), None)


def next_step(games: list[dict], puzzles_done=puzzles.done) -> tuple[dict | None, dict | None]:
    """(the next step, its unfinished game to continue or None). (None, None) once all is done."""
    for step in schedule():
        if step["kind"] == "puzzles":
            if not puzzles_done(step):
                return step, None
            continue
        d = find_game(step, games)
        if d is None or d["result"] == "*":
            return step, d
    return None, None


def step_title(step: dict) -> str:
    if step["kind"] == "match":
        return f"game {step['number']} of {MATCH_GAMES} ({step['opening']})"
    if step["kind"] == "puzzles":
        return f"checkpoint {step['checkpoint']}: puzzle test for {step['agent'].capitalize()}"
    return (f"checkpoint {step['checkpoint']}: {step['agent'].capitalize()} as {step['color']} vs Stockfish "
            f"({step['opening']})")


# ---------- The results table (docs/data/results.json) ----------

def score(d: dict, color: str) -> float:
    return 0.5 if d["winner"] is None else float(d["winner"] == color)


def result_row(step: dict, d: dict) -> dict:
    row = {"key": step["key"], "id": d["id"], "kind": step["kind"], "date": d["date"],
           "opening": step["opening"], "white": d["white"]["name"], "black": d["black"]["name"],
           "result": d["result"], "result_text": d["result_text"], "moves": (len(d["moves"]) + 1) // 2,
           "notebook_lessons": d.get("notebook_lessons")}
    if step["kind"] == "match":
        magnus = "white" if step["magnus_white"] else "black"
        row.update(number=step["number"], magnus_color=magnus, magnus_score=score(d, magnus))
    else:
        row.update(checkpoint=step["checkpoint"], agent=step["agent"].capitalize(),
                   agent_color=step["color"], agent_score=score(d, step["color"]))
    review_ = d.get("review") or {}
    for color in ("white", "black"):
        if color in review_:
            row[f"{color}_accuracy"] = review_[color]["accuracy"]
            row[f"{color}_acpl"] = review_[color]["acpl"]
            row[f"{color}_blunders"] = review_[color]["blunders"]
    # How often Magnus said a notebook rule applied (his RULES line).
    for color in ("white", "black"):
        if d[color]["name"] == "Magnus":
            own = [m for m in d["moves"] if m["color"] == color and m.get("thought_source") == "claude"]
            row["magnus_moves"] = len(own)
            row["magnus_rules_used"] = sum(bool(m.get("rules")) for m in own)
    if "lessons" in d:
        row["new_lessons"] = len(d["lessons"]["new_lessons"])
        row["notebook_after"] = d["lessons"]["notebook_size"]
    row["claude_requests"] = sum((m.get("usage") or {}).get("requests", 0) for m in d["moves"])
    return row


def save_results(games: list[dict], settings: dict) -> Path:
    rows, tests = [], []
    for step in schedule():
        if step["kind"] == "puzzles":
            if (s := puzzles.summary(step)):
                tests.append(s)
        elif (d := find_game(step, games)) and d["result"] != "*":
            rows.append(result_row(step, d))
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps({"settings": settings, "games": rows, "puzzle_tests": tests},
                                       indent=2, ensure_ascii=False), encoding="utf-8")
    return RESULTS_FILE
