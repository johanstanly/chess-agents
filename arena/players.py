"""
Chess players. Every player works the same way, just like the AI agents will:
it looks at the position and SUGGESTS a move as text (plus what it was
thinking). The arbiter then decides whether the suggestion is legal.

The players here cost nothing and are used to test the arbiter:
- RandomPlayer:   always suggests a random legal move.
- SloppyPlayer:   often suggests illegal or unreadable moves (tests retries).
- ScriptedPlayer: plays a fixed list of moves (tests particular endings).
"""

import random
from dataclasses import dataclass, field

import chess

from diary import describe_move


@dataclass
class Suggestion:
    move_text: str          # e.g. "Nf3", "O-O" or "g1f3"
    thought: str            # what the player was thinking
    thought_source: str = "move_description"
    raw: str = ""           # the player's full answer (kept when no move could be read)


@dataclass
class Turn:
    """What a player is told when it is their turn to move."""
    board: chess.Board                  # a copy of the position
    color: str                          # "white" or "black"
    feedback: list = field(default_factory=list)  # arbiter's notes on earlier illegal tries


class Player:
    name = "Player"
    kind = "unknown"

    def info(self) -> dict:
        """How this player is described in the diary."""
        return {"name": self.name, "type": self.kind}

    def suggest(self, turn: Turn) -> Suggestion:
        raise NotImplementedError


class RandomPlayer(Player):
    kind = "random"

    def __init__(self, name: str = "Random", seed: int | None = None):
        self.name = name
        self.rng = random.Random(seed)

    def suggest(self, turn: Turn) -> Suggestion:
        move = self.rng.choice(list(turn.board.legal_moves))
        return Suggestion(turn.board.san(move), describe_move(turn.board, move))


class SloppyPlayer(RandomPlayer):
    """Like RandomPlayer, but about half of its first tries are wrong."""
    kind = "sloppy-test"

    BAD_SUGGESTIONS = ["Ke9", "banana", "", "Qxz9", "O-O-O-O", "e2e5", "Nf3??! maybe"]

    def suggest(self, turn: Turn) -> Suggestion:
        if len(turn.feedback) < 2 and self.rng.random() < 0.5:
            bad = self.rng.choice(self.BAD_SUGGESTIONS + [self.illegal_but_real(turn.board)])
            return Suggestion(bad, "I am not sure about this one...")
        return super().suggest(turn)

    def illegal_but_real(self, board: chess.Board) -> str:
        """A move that looks real but is not allowed here, e.g. a pawn moving 3 squares."""
        return self.rng.choice(["a2a5", "h7h4", "e1e3", "d8d1", "Nb1d2d3", "Kxe8"])


class ScriptedPlayer(Player):
    """Plays the moves in `moves` in order (used by tests)."""
    kind = "scripted-test"

    def __init__(self, moves: list[str], name: str = "Scripted"):
        self.name = name
        self.moves = list(moves)

    def suggest(self, turn: Turn) -> Suggestion:
        return Suggestion(self.moves.pop(0) if self.moves else "", "Following the script.")
