"""
Stockfish on this computer (the file in engines/, not uploaded to GitHub).

Used for:
- StockfishPlayer: the fixed "yardstick" opponent, turned down to its weakest level.
- open_engine(): a full-strength Stockfish for grading moves (see review.py).
"""

from pathlib import Path

import chess
import chess.engine

from players import Player, Suggestion, Turn

ROOT = Path(__file__).resolve().parent.parent
ENGINE_DIR = ROOT / "engines"


def engine_path() -> str:
    """Finds the Stockfish program inside engines/."""
    found = sorted(ENGINE_DIR.rglob("stockfish*.exe")) or sorted(ENGINE_DIR.rglob("stockfish*"))
    programs = [p for p in found if p.is_file() and p.suffix in (".exe", "")]
    if not programs:
        raise SystemExit("Stopped: Stockfish was not found in the engines/ folder.")
    return str(programs[0].resolve())


def open_engine() -> chess.engine.SimpleEngine:
    return chess.engine.SimpleEngine.popen_uci(engine_path())


class StockfishPlayer(Player):
    """Stockfish at a chosen strength. Skill Level 0 is its weakest setting;
    it also only gets a very short time to think."""
    kind = "stockfish"

    def __init__(self, skill: int = 0, think_seconds: float = 0.05, name: str | None = None):
        self.skill = skill
        self.think_seconds = think_seconds
        self.name = name or f"Stockfish (skill {skill})"
        self.engine = open_engine()
        self.engine.configure({"Skill Level": skill, "Threads": 1})

    def info(self) -> dict:
        return {"name": self.name, "type": self.kind, "skill": self.skill,
                "think_seconds": self.think_seconds, "engine": self.engine.id.get("name")}

    def suggest(self, turn: Turn) -> Suggestion:
        result = self.engine.play(turn.board, chess.engine.Limit(time=self.think_seconds))
        san = turn.board.san(result.move)
        return Suggestion(san, f"{self.name} plays {san}.", "engine")

    def close(self) -> None:
        self.engine.quit()
