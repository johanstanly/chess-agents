"""
Opening book: every experiment game starts from a well-known opening, so the
players don't repeat their favourite opening (version 1 was the Ruy Lopez in 8
of 10 games) and Magnus meets many different kinds of positions.

Games 1-20: each opening is played twice, with the colours swapped
(game 1 Magnus is White, game 2 Magnus is Black, both from the first opening).
The Stockfish checkpoint games use two fixed openings.

The book moves are played for the players and saved in the diary with
thought_source "book": they are not graded, studied or put in the mistake library.
"""

import chess

from players import Suggestion

OPENINGS = [
    {"name": "Ruy Lopez", "moves": "e4 e5 Nf3 Nc6 Bb5 a6 Ba4 Nf6"},
    {"name": "Italian Game", "moves": "e4 e5 Nf3 Nc6 Bc4 Bc5 c3 Nf6"},
    {"name": "Sicilian Defence, Najdorf", "moves": "e4 c5 Nf3 d6 d4 cxd4 Nxd4 Nf6 Nc3 a6"},
    {"name": "French Defence", "moves": "e4 e6 d4 d5 Nc3 Nf6"},
    {"name": "Caro-Kann Defence", "moves": "e4 c6 d4 d5 Nc3 dxe4 Nxe4 Bf5"},
    {"name": "Queen's Gambit Declined", "moves": "d4 d5 c4 e6 Nc3 Nf6 Bg5 Be7"},
    {"name": "King's Indian Defence", "moves": "d4 Nf6 c4 g6 Nc3 Bg7 e4 d6"},
    {"name": "English Opening", "moves": "c4 e5 Nc3 Nf6 g3 d5 cxd5 Nxd5"},
    {"name": "Scandinavian Defence", "moves": "e4 d5 exd5 Qxd5 Nc3 Qa5"},
    {"name": "London System", "moves": "d4 d5 Bf4 Nf6 e3 e6 Nf3 c5"},
]

# Checkpoint games against Stockfish: by the colour the agent plays.
CHECKPOINT_OPENINGS = {"white": "Italian Game", "black": "Queen's Gambit Declined"}


def by_name(name: str) -> dict:
    return next(o for o in OPENINGS if o["name"] == name)


def for_match_game(number: int) -> dict:
    """Games 2k-1 and 2k share an opening (with the colours swapped)."""
    return OPENINGS[(number - 1) // 2 % len(OPENINGS)]


def book_moves(opening: dict) -> list[str]:
    return opening["moves"].split()


class OpeningBook:
    """Wraps a player: plays the opening's moves for it, then lets it play.
    Everything else (name, usage, the live view's hooks) goes to the real player."""

    def __init__(self, player, opening: dict):
        self.__dict__.update(player=player, opening=opening, moves=book_moves(opening))

    def __getattr__(self, name):
        return getattr(self.__dict__["player"], name)

    def __setattr__(self, name, value):
        setattr(self.player, name, value)

    def suggest(self, turn):
        ply = len(turn.board.move_stack)
        if ply < len(self.moves):
            self.player.last_usage = None   # no Claude request was made for this move
            return Suggestion(self.moves[ply], f"Opening: {self.opening['name']}.", "book")
        return self.player.suggest(turn)


def check_book() -> list[str]:
    """Problems with the opening list (every move must be legal), for the tests."""
    problems = []
    for o in OPENINGS:
        board = chess.Board()
        try:
            for san in book_moves(o):
                board.push_san(san)
        except ValueError as err:
            problems.append(f"{o['name']}: {err}")
    return problems
