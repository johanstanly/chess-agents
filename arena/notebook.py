"""
Magnus's learning material: his notebook and his mistake library.

The notebook (notebook/magnus_notebook.md): at most NOTEBOOK_CAP general rules,
each tied to a phase of the game and a short example. After every game against
Hans (win, draw or loss) he is shown his worst moves (found by Stockfish, with
Stockfish's better move and how his move was punished) and rewrites the whole
notebook: keeping, sharpening, merging or replacing rules. One Claude request.
- Every rule ever written is also kept in notebook/archive.jsonl.
- A dated copy of the notebook is saved in notebook/history/ every time it changes.

The mistake library (notebook/mistakes.jsonl): every mistake and blunder Magnus
made against Hans, with the position, his thought, Stockfish's better move and
how it was punished. Before each move, the MISTAKES_SHOWN past mistakes from the
most similar positions (same phase of the game, most similar material) are
added to his message. No Claude request: the program picks them.

Hans (the control) has neither.
"""

import json
import re
from datetime import datetime
from pathlib import Path

import chess
import chess.engine

from claude_agent import PROMPTS, ClaudeAgent, board_diagram

ROOT = Path(__file__).resolve().parent.parent
NOTEBOOK_DIR = ROOT / "notebook"
NOTEBOOK = NOTEBOOK_DIR / "magnus_notebook.md"
MISTAKES = NOTEBOOK_DIR / "mistakes.jsonl"

# Settings (locked for the experiment by experiment.py).
NOTEBOOK_CAP = 15                        # the most rules in the notebook
WORST_MOVES = 3                          # how many of his worst moves Magnus studies after a game
MISTAKES_SHOWN = 2                       # past mistakes shown with each move
LIBRARY_LABELS = ("mistake", "blunder")  # which graded moves go into the mistake library
REFUTATION_PLIES = 6                     # how far "how it was punished" is shown (half-moves)
REFUTATION_DEPTH = 16

PHASES = ("opening", "middlegame", "endgame")
HEADING = "Magnus's notebook: rules from my earlier games"


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


# ---------- Game phase and material (for choosing similar past mistakes) ----------

PIECE_VALUES = {chess.KNIGHT: 3, chess.BISHOP: 3, chess.ROOK: 5, chess.QUEEN: 9}
COUNTED = (chess.PAWN, chess.KNIGHT, chess.BISHOP, chess.ROOK, chess.QUEEN)
WEIGHTS = (1, 3, 3, 5, 9) * 2


def game_phase(board: chess.Board) -> str:
    """Opening = the first 12 moves; endgame = little material left (or no queens
    and not much else); middlegame = everything in between."""
    if board.fullmove_number <= 12:
        return "opening"
    pieces = sum(v * len(board.pieces(p, c)) for p, v in PIECE_VALUES.items() for c in chess.COLORS)
    queens = len(board.pieces(chess.QUEEN, chess.WHITE)) + len(board.pieces(chess.QUEEN, chess.BLACK))
    if pieces <= 26 or (queens == 0 and pieces <= 40):
        return "endgame"
    return "middlegame"


def material(board: chess.Board, color: str) -> list[int]:
    """Piece counts: the player's pawns, knights, bishops, rooks, queens, then the opponent's."""
    me = chess.WHITE if color == "white" else chess.BLACK
    return [len(board.pieces(p, side)) for side in (me, not me) for p in COUNTED]


def material_distance(a: list[int], b: list[int]) -> int:
    return sum(w * abs(x - y) for w, x, y in zip(WEIGHTS, a, b))


def is_book(m: dict) -> bool:
    return m.get("thought_source") == "book"


def position_before(d: dict, m: dict) -> str:
    return d["start_fen"] if m["ply"] == 1 else d["moves"][m["ply"] - 2]["fen_after"]


def move_label(m: dict) -> str:
    return f"{m['move_number']}{'.' if m['color'] == 'white' else '...'} {m['san']}"


# ---------- What Magnus is shown after a game ----------

def worst_moves(d: dict, color: str, count: int = WORST_MOVES) -> list[dict]:
    """The player's own moves (not book moves) that lost the most winning chances."""
    own = [m for m in d["moves"] if m["color"] == color and "review" in m and not is_book(m)]
    own = [m for m in own if m["review"]["win_before"] > m["review"]["win_after"]]
    own.sort(key=lambda m: m["review"]["win_after"] - m["review"]["win_before"])
    return sorted(own[:count], key=lambda m: m["ply"])


def add_refutations(d: dict, color: str, engine: chess.engine.SimpleEngine) -> None:
    """For each of the player's worst moves and library mistakes: Stockfish's best
    play right after it, i.e. how the move was punished. Saved in the move's review."""
    wanted = {m["ply"] for m in worst_moves(d, color)}
    wanted |= {m["ply"] for m in d["moves"] if m["color"] == color and not is_book(m)
               and (m.get("review") or {}).get("label") in LIBRARY_LABELS}
    engine.configure({"Threads": 1})
    board = chess.Board(d["start_fen"])
    for m in d["moves"]:
        board.push_uci(m["uci"])
        if m["ply"] in wanted and "refutation" not in m["review"] and not board.is_game_over():
            info = engine.analyse(board, chess.engine.Limit(depth=REFUTATION_DEPTH), game=object())
            pv = (info.get("pv") or [])[:REFUTATION_PLIES]
            m["review"]["refutation"] = board.variation_san(pv) if pv else ""


def describe_mistake(d: dict, m: dict) -> str:
    r = m["review"]
    board = chess.Board(position_before(d, m))
    better = f"Stockfish preferred {r['best']}. " if r.get("best") and r["best"] != m["san"] else ""
    punished = f"How it was punished (Stockfish's best play after your move): {r['refutation']}\n" \
        if r.get("refutation") else ""
    return (f"\nMove {move_label(m)} ({r['label'] or 'small slip'})\n"
            f"Position before your move:\n{board_diagram(board)}\n"
            f"You played {m['san']}. {better}Your chances of winning went from "
            f"{r['win_before']:.0f}% to {r['win_after']:.0f}%.\n"
            f"{punished}"
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
        size=len(notebook.lessons()),
        cap=NOTEBOOK_CAP,
        notebook=notebook.text() or "(empty)",
    )


def read_lessons(answer: str, limit: int) -> list[str]:
    """Finds the LESSON lines ("phase | rule | example"), tolerating decoration
    such as **LESSON 1:**. Each becomes one notebook line: "[phase] rule Example: ..."."""
    found = re.findall(r"\bLESSON\b[\s*_`\d.]*:[\s*_`]*(.+)", answer, re.I)
    lessons = []
    for text in found:
        text = " ".join(text.replace("*", "").split())
        parts = [p.strip() for p in text.split("|")]
        if len(parts) >= 2 and parts[0].lower() in PHASES:
            text = f"[{parts[0].lower()}] {parts[1]}"
            if len(parts) > 2 and parts[2]:
                text += f" Example: {' | '.join(parts[2:])}"
        if text and text not in lessons:
            lessons.append(text)
    return lessons[:limit]


# ---------- The lesson-writing step ----------

def write_lessons(d: dict, color: str, agent: ClaudeAgent, notebook: Notebook | None = None) -> dict:
    """Magnus studies a game and rewrites his notebook (call add_refutations first).
    Returns a record of what happened (also stored in the game's diary)."""
    notebook = notebook or Notebook()
    old = notebook.lessons()
    moves = worst_moves(d, color)
    record = {"worst_moves": [m["ply"] for m in moves], "new_lessons": [], "dropped": 0, "requests": 0,
              "notebook_size": len(old)}
    if not moves:
        record["problem"] = "no mistakes to study in this game"
        return record
    system = (PROMPTS / "lessons_system.txt").read_text(encoding="utf-8")
    agent.game_id = d["id"]
    answer = agent.ask(lessons_message(d, color, notebook), system_prompt=system)
    record["requests"] = 1
    lessons = read_lessons(answer, NOTEBOOK_CAP)
    if not lessons:
        record["problem"] = "no LESSON lines in the answer: " + " ".join(answer.split())[:200]
        return record
    record["new_lessons"] = [x for x in lessons if x not in old]
    record["dropped"] = len([x for x in old if x not in lessons])
    record["notebook_size"] = len(lessons)
    notebook.add_to_archive(record["new_lessons"], d["id"])
    record["copy"] = notebook.save(lessons, f"after-{d['id']}").name
    return record


# ---------- The mistake library ----------

class MistakeLibrary:
    def __init__(self, path: Path = MISTAKES):
        self.path = path

    def entries(self) -> list[dict]:
        if not self.path.exists():
            return []
        return [json.loads(line) for line in self.path.read_text(encoding="utf-8").splitlines() if line.strip()]

    def add_game(self, d: dict, color: str) -> int:
        """Adds the player's mistakes and blunders from a graded game (call
        add_refutations first). Returns how many were added; never adds one twice."""
        known = {(e["game"], e["ply"]) for e in self.entries()}
        new = []
        for m in d["moves"]:
            r = m.get("review") or {}
            if m["color"] != color or is_book(m) or r.get("label") not in LIBRARY_LABELS \
                    or (d["id"], m["ply"]) in known:
                continue
            board = chess.Board(position_before(d, m))
            new.append({"game": d["id"], "game_title": d["title"], "ply": m["ply"], "move": move_label(m),
                        "color": color, "fen": board.fen(), "san": m["san"], "thought": m["thought"],
                        "best": r.get("best"), "refutation": r.get("refutation", ""),
                        "win_before": r["win_before"], "win_after": r["win_after"], "label": r["label"],
                        "phase": game_phase(board), "material": material(board, color)})
        if new:
            self.path.parent.mkdir(parents=True, exist_ok=True)
            with open(self.path, "a", encoding="utf-8") as f:
                for e in new:
                    f.write(json.dumps(e, ensure_ascii=False) + "\n")
        return len(new)

    def similar(self, board: chess.Board, color: str, count: int = MISTAKES_SHOWN) -> list[dict]:
        """The past mistakes from the most similar positions: same phase of the game,
        then the closest material; the most recent first when equally close."""
        phase, mine = game_phase(board), material(board, color)
        entries = list(enumerate(self.entries()))
        same = [(i, e) for i, e in entries if e["phase"] == phase]
        same.sort(key=lambda ie: (material_distance(ie[1]["material"], mine), -ie[0]))
        return [e for _, e in same[:count]]

    def text(self, board: chess.Board, color: str, count: int = MISTAKES_SHOWN) -> str:
        parts = []
        for e in self.similar(board, color, count):
            better = f" Stockfish preferred {e['best']}." if e.get("best") and e["best"] != e["san"] else ""
            punished = f" How it was punished: {e['refutation']}." if e.get("refutation") else ""
            parts.append(f"- {e['game_title']}, move {e['move']} (you were {e['color'].capitalize()}, "
                         f"{e['label']}):\n{board_diagram(chess.Board(e['fen']))}\n"
                         f"You played {e['san']}, thinking: \"{e['thought']}\"{better}{punished} "
                         f"Your chances of winning fell from {e['win_before']:.0f}% to {e['win_after']:.0f}%.")
        return "\n".join(parts)
