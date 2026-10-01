"""
The live view's feed: while a game is being played, this keeps
docs/live/status.json up to date, and the live page (docs/live.html) reads it
about once a second.

States:  thinking  a player has been asked for a move
         writing   Claude's answer is arriving; "thought" holds it so far
         moved     a move was played ("ply" moves are now in the diary)
         finished  the game is over ("graded" becomes true once Stockfish has graded it)
         stopped   Claude stopped answering; the game can be continued later

The file is only on your computer (it is not uploaded to GitHub).
Also here: DemoPlayer, a free stand-in for Claude that pauses and "types"
made-up thoughts, to test the live page without using any Claude requests.
"""

import json
import os
import random
import re
import time
from datetime import datetime
from pathlib import Path

from players import RandomPlayer, Suggestion, Turn

ROOT = Path(__file__).resolve().parent.parent
LIVE_FILE = ROOT / "docs" / "live" / "status.json"


# The live page types each thought out, leaves it up to be read, then moves the
# piece by hand: about 5 seconds per move, a little more only for long thoughts.
# The runner waits that long before asking the next player, so nothing is rushed
# or overlaps. Same rule as docs/js/liveview.js.
TYPE_SPEED = 40          # letters per second
MOVE_SECONDS = 1.2       # the piece being picked up and put down
VIEW_SECONDS = 5.0       # the whole move
MIN_READ = 1.5           # reading time left after even a long thought is typed


def viewing_seconds(thought: str) -> float:
    """How long the live page needs to show a move's thought and play the move."""
    typing = len(thought) / TYPE_SPEED
    reading = max(MIN_READ, VIEW_SECONDS - MOVE_SECONDS - typing)
    return typing + reading + MOVE_SECONDS


def thought_so_far(text: str) -> str:
    """The THOUGHT part of a partly written answer, without the MOVE line."""
    start = re.search(r"THOUGHT\b[\s*_`]*:[\s*_`]*", text, re.I)
    if not start:
        return ""
    rest = text[start.end():]
    end = re.search(r"\n[\s*_`]*M|[\s*_`]*\bMOVE\b", rest)   # the MOVE part has begun
    return " ".join((rest[:end.start()] if end else rest).replace("*", "").split())


class LiveStatus:
    def __init__(self, game_id: str, white: str, black: str, path: Path = LIVE_FILE):
        self.path = path
        self.state = {"game_id": game_id, "file": f"{game_id}.json", "white": white, "black": black,
                      "state": "starting", "color": None, "player": None, "thought": "", "ply": 0,
                      "graded": False, "seq": 0}

    def write(self, **changes) -> None:
        self.state.update(changes, seq=self.state["seq"] + 1,
                          updated=datetime.now().isoformat(timespec="seconds"))
        self.path.parent.mkdir(parents=True, exist_ok=True)
        temp = self.path.with_suffix(".tmp")
        temp.write_text(json.dumps(self.state, ensure_ascii=False), encoding="utf-8")
        for _ in range(20):   # the browser may be reading the file at this very moment
            try:
                os.replace(temp, self.path)
                return
            except PermissionError:
                time.sleep(0.05)

    # Hooks for the arbiter and the players.
    def turn(self, color: str, player) -> None:
        if hasattr(player, "on_text"):
            player.on_text = self.text
        self.write(state="thinking", color=color, player=player.name, thought="")

    def text(self, answer_so_far: str) -> None:
        self.write(state="writing", thought=thought_so_far(answer_so_far))

    def moved(self, record: dict) -> None:
        self.write(state="moved", color=record["color"], ply=record["ply"], san=record["san"],
                   thought=record["thought"])

    def finished(self, d: dict) -> None:
        self.write(state="finished", ply=len(d["moves"]), result=d["result"], result_text=d["result_text"])

    def stopped(self, reason: str) -> None:
        self.write(state="stopped", message=reason)


DEMO_THOUGHTS = [
    "I want to keep my pieces active and see what my opponent is planning.",
    "This looks natural. I should watch my king and not leave anything hanging.",
    "Let me improve my worst piece before starting anything sharp.",
    "Hmm, that last move was strange. I will answer calmly and keep control.",
    "Development first, then I can think about an attack.",
]


class DemoPlayer(RandomPlayer):
    """Plays random moves slowly, 'typing' made-up thoughts like Claude does.
    Free: it never asks Claude. Only for testing the live view."""
    kind = "demo"

    def __init__(self, name: str, seed: int | None = None, think: tuple = (2.0, 5.0)):
        super().__init__(name, seed)
        self.think = think
        self.on_text = None

    def suggest(self, turn: Turn) -> Suggestion:
        time.sleep(self.rng.uniform(*self.think))
        move = self.rng.choice(list(turn.board.legal_moves))
        san = turn.board.san(move)
        thought = f"(demo) {self.rng.choice(DEMO_THOUGHTS)} I play {san}."
        answer = "THOUGHT: "
        for word in thought.split():
            answer += word + " "
            if self.on_text:
                self.on_text(answer)
            time.sleep(0.05)
        return Suggestion(san, thought, "demo")


def demo_players(seed: int | None = None) -> tuple[DemoPlayer, DemoPlayer]:
    rng = random.Random(seed)
    return DemoPlayer("Magnus", rng.randint(0, 10**6)), DemoPlayer("Hans", rng.randint(0, 10**6))
