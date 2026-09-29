"""
Offline checks for the Claude agent. No real Claude requests are made:
a pretend Claude gives prepared answers. Costs nothing.

Run:  python tests/check_agent.py
"""

import os
import sys
import tempfile
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "arena"))
from arbiter import play_game  # noqa: E402
from claude_agent import ClaudeAgent  # noqa: E402
from players import RandomPlayer, Turn  # noqa: E402

failures = 0


def check(ok: bool, text: str) -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'}  {text}")
    failures += not ok


# (Claude's answer, expected move text, words expected in the thought)
ANSWERS = [
    ("MOVE: Nf3\nTHOUGHT: I develop my knight.", "Nf3", "develop my knight"),
    ("**MOVE:** Nf3\n**THOUGHT:** Develop.", "Nf3", "Develop."),
    ("MOVE: `e4`\nTHOUGHT: Centre.", "e4", "Centre."),
    ("Move: O-O.\nThought: King safety\nover several lines.", "O-O", "King safety over several lines."),
    ("I'll move my knight here.\nMOVE: Nc3\nTHOUGHT: Knight to c3.", "Nc3", "Knight to c3."),
    ("I think Nf3 is best.", "", "I think Nf3 is best."),
]


class PretendClaude(ClaudeAgent):
    """Answers with prepared replies instead of asking the real Claude."""

    def __init__(self, replies, **kwargs):
        super().__init__(**kwargs)
        self.replies = list(replies)
        self.messages = []

    def ask(self, message, system_prompt=None):
        self.messages.append(message)
        self.last_usage = {"input_tokens": 1000, "output_tokens": 50, "seconds": 1.0}
        return self.replies.pop(0)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("1. Reading Claude's answers")
    for answer, move, thought in ANSWERS:
        s = ClaudeAgent.read_answer(answer)
        check(s.move_text == move and thought in s.thought,
              f"{answer.splitlines()[0][:40]!r:44} -> move {s.move_text!r}")

    print("\n2. Paid API safety stop")
    os.environ["ANTHROPIC_API_KEY"] = "test-not-a-real-key"
    try:
        ClaudeAgent("Claude")
        check(False, "agent refused to start with an API key set")
    except SystemExit as stop:
        check("paid API" in str(stop), "agent refuses to start when an API key is set")
    finally:
        del os.environ["ANTHROPIC_API_KEY"]

    print("\n3. Retries in a real game (pretend Claude)")
    agent = PretendClaude(["MOVE: Ke9\nTHOUGHT: Oops.", "MOVE: e4\nTHOUGHT: Better.",
                           "MOVE: d4\nTHOUGHT: Centre."], name="Pretend")
    with tempfile.TemporaryDirectory() as tmp:
        d = play_game(agent, RandomPlayer(seed=1), "pretend", "pretend", games_dir=Path(tmp),
                      move_limit=2, log=lambda *a: None)
    first = d["moves"][0]
    check(first["san"] == "e4" and first["illegal_attempts"] == 1
          and first["illegal_suggestions"] == ["Ke9"], "illegal 'Ke9' refused, then 'e4' accepted")
    check("refused your previous answer" in agent.messages[1] and "Ke9" in agent.messages[1],
          "the retry message tells Claude why it was refused")
    check(first["usage"] == {"requests": 2, "input_tokens": 2000, "output_tokens": 100, "seconds": 2.0},
          "usage of both requests is recorded for the move")
    check(first["thought"] == "Better." and first["thought_source"] == "claude",
          "the thought of the accepted answer is saved")

    print("\n4. Notebook (for Agent A in Phase 9)")
    with tempfile.TemporaryDirectory() as tmp:
        book = Path(tmp) / "notebook.md"
        book.write_text("1. Check whose queen is attacked before moving.", encoding="utf-8")
        learner = ClaudeAgent("Agent A", notebook_path=book)
        control = ClaudeAgent("Agent B")
        board = chess.Board()
        check("Check whose queen is attacked" in learner.turn_message(Turn(board, "white")),
              "Agent A's message contains its notebook")
        check("notebook" not in control.turn_message(Turn(board, "white")).lower(),
              "Agent B's message has no notebook")

    print(f"\n{'ALL CHECKS PASSED' if failures == 0 else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
