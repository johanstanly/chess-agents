"""
Automatic checks for diary files.

1. Every diary in docs/games/ is replayed move by move with python-chess.
   Each move must be legal and the saved board position must match.
2. A deliberately broken game (with an illegal move) must be refused.

Run:  python tests/check_diaries.py
"""

import json
import sys
import tempfile
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "arena"))
import diary  # noqa: E402
import make_sample_diaries  # noqa: E402

REQUIRED_MOVE_FIELDS = ["ply", "color", "san", "from", "to", "piece", "fen_after", "thought"]


def check_diary(path: Path) -> list[str]:
    problems = []
    d = json.loads(path.read_text(encoding="utf-8"))
    board = chess.Board(d["start_fen"])
    for i, m in enumerate(d["moves"], start=1):
        missing = [f for f in REQUIRED_MOVE_FIELDS if f not in m]
        if missing:
            problems.append(f"half-move {i}: missing {missing}")
            break
        move = chess.Move.from_uci(m["uci"])
        if move not in board.legal_moves:
            problems.append(f"half-move {i} ({m['san']}): illegal")
            break
        if board.san(move) != m["san"]:
            problems.append(f"half-move {i}: notation {m['san']} should be {board.san(move)}")
        board.push(move)
        if board.fen() != m["fen_after"]:
            problems.append(f"half-move {i} ({m['san']}): saved board position is wrong")
            break
    if d["result"] not in ("1-0", "0-1", "1/2-1/2", "*"):
        problems.append(f"unknown result {d['result']}")
    return problems


def check_illegal_game_is_refused() -> list[str]:
    # Lasker vs Thomas, but with an impossible 3rd move for White (knight to h8).
    broken = ('[Event "Broken"]\n[White "A"]\n[Black "B"]\n[Result "*"]\n\n'
              '1. d4 e6 2. Nf3 f5 3. Nh8 Nf6 *\n')
    with tempfile.TemporaryDirectory() as tmp:
        pgn = Path(tmp) / "broken.pgn"
        pgn.write_text(broken, encoding="utf-8")
        before = set(diary.GAMES_DIR.glob("*.json"))
        saved = make_sample_diaries.convert(pgn)
        after = set(diary.GAMES_DIR.glob("*.json"))
    if saved or after != before:
        return ["a game with an illegal move was NOT refused"]
    return []


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    failures = 0
    games = list(diary.GAMES_DIR.glob("*.json")) + list(diary.FIXTURES_DIR.glob("*.json"))
    for path in sorted(games):
        if path.name == "index.json":
            continue
        problems = check_diary(path)
        print(f"{'PASS' if not problems else 'FAIL'}  {path.name}")
        for p in problems:
            print(f"      {p}")
        failures += bool(problems)

    print("\nIllegal-move test (this game SHOULD be refused):")
    problems = check_illegal_game_is_refused()
    print(f"{'PASS' if not problems else 'FAIL'}  illegal game refused, no diary saved")
    for p in problems:
        print(f"      {p}")
    failures += bool(problems)

    print(f"\n{'ALL CHECKS PASSED' if failures == 0 else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
