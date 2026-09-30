"""
Magnus's notebook: the lessons he reads before every move.

After each game Magnus does not win against Hans, he gets ONE extra Claude
request: he is shown his worst moves (found by Stockfish, with Stockfish's
better move) and writes up to LESSONS_PER_GAME general lessons.

- The notebook holds at most NOTEBOOK_CAP lessons. When it is fuller than
  that, Magnus gets one more request to merge them down to MERGE_TARGET.
- Every lesson ever written is also kept in notebook/archive.jsonl.
- A dated copy of the notebook is saved in notebook/history/ every time it changes.

Hans (the control) never has a notebook.
"""

import json
import re
from datetime import datetime
from pathlib import Path

import chess

from claude_agent import PROMPTS, ClaudeAgent, board_diagram

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_DIR = ROOT / "notebook"
NOTEBOOK = NOTEBOOK_DIR / "magnus_notebook.md"

# Settings (they may be raised later, e.g. with more games).
NOTEBOOK_CAP = 15       # the most lessons Magnus reads during a game
MERGE_TARGET = 10       # when the notebook overflows, it is merged down to this many
LESSONS_PER_GAME = 3    # new lessons after one game
WORST_MOVES = 3         # how many of his worst moves Magnus is shown

HEADING = "Magnus's notebook: lessons from my earlier games"


class Notebook:
    """The notebook file plus its archive and dated copies (all in one folder)."""

    def __init__(self, folder: Path = NOTEBOOK_DIR):
        self.folder = folder
        self.path = folder / NOTEBOOK.name
        self.archive = folder / "archive.jsonl"
        self.history = folder / "history"

    def lessons(self) -> list[str]:
        if not self.path.exists():
            return []
        return [m.group(1).strip() for m in re.finditer(r"^\d+\.\s+(.+)$",
                                                         self.path.read_text(encoding="utf-8"), re.M)]

    def text(self, lessons: list[str] | None = None) -> str:
        lessons = self.lessons() if lessons is None else lessons
        return "\n".join(f"{i}. {lesson}" for i, lesson in enumerate(lessons, start=1))

    def save(self, lessons: list[str], reason: str) -> Path:
        """Writes the notebook and a dated copy of it; returns the copy's path."""
        self.folder.mkdir(parents=True, exist_ok=True)
        content = f"# {HEADING}\n\n{self.text(lessons)}\n"
        self.path.write_text(content, encoding="utf-8")
        self.history.mkdir(exist_ok=True)
        stem = f"{datetime.now():%Y-%m-%d-%H%M%S}-{reason}"
        copy, n = self.history / f"{stem}.md", 2
        while copy.exists():   # never overwrite an earlier copy
            copy, n = self.history / f"{stem}-{n}.md", n + 1
        copy.write_text(content, encoding="utf-8")
        return copy

    def add_to_archive(self, lessons: list[str], game_id: str) -> None:
        self.folder.mkdir(parents=True, exist_ok=True)
        with open(self.archive, "a", encoding="utf-8") as f:
            for lesson in lessons:
                f.write(json.dumps({"time": f"{datetime.now():%Y-%m-%d %H:%M:%S}",
                                    "game": game_id, "lesson": lesson}, ensure_ascii=False) + "\n")


# ---------- What Magnus is shown after a game ----------

def worst_moves(d: dict, color: str, count: int = WORST_MOVES) -> list[dict]:
    """The player's moves that lost the most winning chances (needs Stockfish's review)."""
    own = [m for m in d["moves"] if m["color"] == color and "review" in m]
    own = [m for m in own if m["review"]["win_before"] > m["review"]["win_after"]]
    own.sort(key=lambda m: m["review"]["win_after"] - m["review"]["win_before"])
    return sorted(own[:count], key=lambda m: m["ply"])


def position_before(d: dict, m: dict) -> str:
    return d["start_fen"] if m["ply"] == 1 else d["moves"][m["ply"] - 2]["fen_after"]


def describe_mistake(d: dict, m: dict) -> str:
    dots = "." if m["color"] == "white" else "..."
    r = m["review"]
    board = chess.Board(position_before(d, m))
    better = f"Stockfish preferred {r['best']}." if r.get("best") and r["best"] != m["san"] else ""
    return (f"\nMove {m['move_number']}{dots} {m['san']} ({r['label'] or 'small slip'})\n"
            f"Position before your move:\n{board_diagram(board)}\n"
            f"You played {m['san']}. {better} Your chances of winning went from "
            f"{r['win_before']:.0f}% to {r['win_after']:.0f}%.\n"
            f"What you thought at the time: \"{m['thought']}\"\n")


def lessons_message(d: dict, color: str, notebook: Notebook) -> str:
    moves = worst_moves(d, color)
    history = chess.Board(d["start_fen"]).variation_san([chess.Move.from_uci(m["uci"]) for m in d["moves"]])
    template = (PROMPTS / "lessons_turn.txt").read_text(encoding="utf-8")
    return template.format(
        color="White" if color == "white" else "Black",
        result_text=d["result_text"],
        history=history,
        count=len(moves),
        worst_moves="".join(describe_mistake(d, m) for m in moves),
        notebook=notebook.text() or "(empty)",
        max_lessons=LESSONS_PER_GAME,
    )


def merge_message(lessons: list[str], notebook: Notebook) -> str:
    template = (PROMPTS / "merge_turn.txt").read_text(encoding="utf-8")
    return template.format(count=len(lessons), target=MERGE_TARGET, notebook=notebook.text(lessons))


def read_lessons(answer: str, limit: int) -> list[str]:
    """Finds the LESSON lines, tolerating decoration such as **LESSON 1:**."""
    found = re.findall(r"\bLESSON\b[\s*_`\d.]*:[\s*_`]*(.+)", answer, re.I)
    lessons = [" ".join(t.replace("*", "").split()) for t in found]
    return [t for t in lessons if t][:limit]


# ---------- The lesson-writing step ----------

def write_lessons(d: dict, color: str, agent: ClaudeAgent, notebook: Notebook | None = None) -> dict:
    """Magnus studies a game he did not win and updates his notebook.
    Returns a record of what happened (also stored in the game's diary)."""
    notebook = notebook or Notebook()
    system = (PROMPTS / "lessons_system.txt").read_text(encoding="utf-8")
    agent.game_id = d["id"]
    answer = agent.ask(lessons_message(d, color, notebook), system_prompt=system)
    new = read_lessons(answer, LESSONS_PER_GAME)
    record = {"worst_moves": [m["ply"] for m in worst_moves(d, color)], "new_lessons": new,
              "merged": False, "requests": 1}
    if not new:
        record["problem"] = "no LESSON lines in the answer: " + " ".join(answer.split())[:200]
        return record
    notebook.add_to_archive(new, d["id"])
    lessons = notebook.lessons() + new
    if len(lessons) > NOTEBOOK_CAP:
        merged = read_lessons(agent.ask(merge_message(lessons, notebook), system_prompt=system), MERGE_TARGET)
        record["requests"] += 1
        if merged:
            lessons, record["merged"] = merged, True
        else:
            lessons = lessons[-NOTEBOOK_CAP:]   # merging failed: keep the newest lessons
            record["problem"] = "merging gave no lessons; kept the newest ones"
    record["notebook_size"] = len(lessons)
    record["copy"] = notebook.save(lessons, f"after-{d['id']}").name
    return record
