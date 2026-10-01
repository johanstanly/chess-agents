"""
The experiment (Phase 10): its locked settings, its schedule and its results table.

Schedule (32 games):
  checkpoint 0    Magnus and Hans each play Stockfish twice (once as White, once as Black)
  games 1-10      Magnus vs Hans; after each game Magnus does not win, he writes lessons
  checkpoint 10   the same 4 Stockfish games again
  games 11-20     Magnus vs Hans
  checkpoint 20   the same 4 Stockfish games again

The settings are locked in experiment.json (written by reset_experiment.py) and
must not change until the experiment is over; otherwise later games could not be
compared with earlier ones. The prompts are locked by their fingerprints: if a
prompt file is edited, the runner refuses to continue.
"""

import hashlib
import json
from datetime import datetime
from pathlib import Path

import notebook
import review

ROOT = Path(__file__).resolve().parent.parent
SETTINGS_FILE = ROOT / "experiment.json"
RESULTS_FILE = ROOT / "docs" / "data" / "results.json"
PROMPTS_DIR = ROOT / "prompts"

MATCH_GAMES = 20
CHECKPOINTS = (0, 10, 20)               # yardstick games are played before game 1, after game 10 and after game 20
YARDSTICK_SKILL = 0
YARDSTICK_THINK_SECONDS = 0.05


def prompt_fingerprints() -> dict:
    """A short fingerprint of every prompt file: it changes if even one letter changes."""
    return {p.name: hashlib.sha256(p.read_bytes()).hexdigest()[:16] for p in sorted(PROMPTS_DIR.glob("*.txt"))}


def current_settings(model: str, effort: str) -> dict:
    """Everything that must stay the same for the whole experiment."""
    return {
        "model": model,
        "effort": effort,
        "match_games": MATCH_GAMES,
        "checkpoints": list(CHECKPOINTS),
        "yardstick_skill": YARDSTICK_SKILL,
        "yardstick_think_seconds": YARDSTICK_THINK_SECONDS,
        "review_depth": review.DEPTH,
        "notebook_cap": notebook.NOTEBOOK_CAP,
        "merge_target": notebook.MERGE_TARGET,
        "lessons_per_game": notebook.LESSONS_PER_GAME,
        "worst_moves": notebook.WORST_MOVES,
        "prompts": prompt_fingerprints(),
    }


def lock(model: str, effort: str) -> dict:
    settings = {"started": datetime.now().isoformat(timespec="seconds"), **current_settings(model, effort)}
    SETTINGS_FILE.write_text(json.dumps(settings, indent=2), encoding="utf-8")
    return settings


def load() -> dict | None:
    return json.loads(SETTINGS_FILE.read_text(encoding="utf-8")) if SETTINGS_FILE.exists() else None


def changes_since_lock(settings: dict) -> list[str]:
    """What differs from the locked settings (empty if nothing)."""
    now = current_settings(settings["model"], settings["effort"])
    return [f"{key}: locked {settings.get(key)!r}, now {value!r}"
            for key, value in now.items() if settings.get(key) != value]


# ---------- The schedule ----------

def schedule() -> list[dict]:
    """Every game of the experiment, in order. "key" is the end of the game's id."""
    steps = []

    def checkpoint(n: int) -> None:
        for agent in ("magnus", "hans"):
            for color in ("white", "black"):
                steps.append({"key": f"checkpoint-{n:02d}-{agent}-{color}", "kind": "yardstick",
                              "checkpoint": n, "agent": agent, "color": color})

    for number in range(MATCH_GAMES + 1):
        if number in CHECKPOINTS:
            checkpoint(number)
        if number < MATCH_GAMES:
            steps.append({"key": f"match-{number + 1:02d}", "kind": "match", "number": number + 1,
                          "magnus_white": (number + 1) % 2 == 1})   # Magnus is White in odd games
    return steps


def find_game(step: dict, games: list[dict]) -> dict | None:
    return next((d for d in games if d["id"].endswith("-" + step["key"])), None)


def next_step(games: list[dict]) -> tuple[dict | None, dict | None]:
    """(the next game to play, its unfinished diary to continue or None).
    (None, None) once every game is finished."""
    for step in schedule():
        d = find_game(step, games)
        if d is None or d["result"] == "*":
            return step, d
    return None, None


def step_title(step: dict) -> str:
    if step["kind"] == "match":
        return f"game {step['number']} of {MATCH_GAMES}"
    return f"checkpoint {step['checkpoint']}: {step['agent'].capitalize()} as {step['color']} vs Stockfish"


# ---------- The results table (docs/data/results.json) ----------

def score(d: dict, color: str) -> float:
    return 0.5 if d["winner"] is None else float(d["winner"] == color)


def result_row(step: dict, d: dict) -> dict:
    row = {"key": step["key"], "id": d["id"], "kind": step["kind"], "date": d["date"],
           "white": d["white"]["name"], "black": d["black"]["name"],
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
    if "lessons" in d:
        row["new_lessons"] = len(d["lessons"]["new_lessons"])
        row["notebook_after"] = d["lessons"]["notebook_size"]
    row["claude_requests"] = sum((m.get("usage") or {}).get("requests", 0) for m in d["moves"])
    return row


def save_results(games: list[dict], settings: dict) -> Path:
    rows = [result_row(step, d) for step in schedule()
            if (d := find_game(step, games)) and d["result"] != "*"]
    RESULTS_FILE.parent.mkdir(parents=True, exist_ok=True)
    RESULTS_FILE.write_text(json.dumps({"settings": settings, "games": rows}, indent=2, ensure_ascii=False),
                            encoding="utf-8")
    return RESULTS_FILE
