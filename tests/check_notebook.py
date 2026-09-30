"""
Automatic checks for Magnus's notebook and the Magnus vs Hans series (Phase 9).
No real Claude requests: a pretend Claude gives prepared answers. Costs nothing.
Needs Stockfish in engines/ (to grade the practice game).

1. Lesson lines are read correctly from Claude's answers.
2. Magnus's move message contains his notebook; Hans's does not.
3. Colours swap every game, and a stopped game is continued.
4. A finished game Magnus did not win (random moves standing in for Claude)
   triggers lesson-writing: he is shown his worst moves with Stockfish's
   better move, and the notebook, archive and dated copy are all updated.
5. A full notebook is merged down, and the archive keeps every lesson.

Run:  python tests/check_notebook.py
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "arena"))
sys.path.insert(0, str(ROOT / "tests"))
import chess  # noqa: E402

import notebook as nb  # noqa: E402
from arbiter import play_game  # noqa: E402
from check_agent import PretendClaude  # noqa: E402
from play import needs_lessons, next_game  # noqa: E402
from players import RandomPlayer, Turn  # noqa: E402

failures = 0


def check(ok: bool, text: str) -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'}  {text}")
    failures += not ok


def fake_game(number: int, magnus_white: bool, result: str) -> dict:
    names = ("Magnus", "Hans") if magnus_white else ("Hans", "Magnus")
    return {"id": f"2026-10-01-1200-match-{number:02d}", "result": result,
            "winner": {"1-0": "white", "0-1": "black"}.get(result),
            "white": {"name": names[0]}, "black": {"name": names[1]}}


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("1. Reading lessons from Claude's answers")
    answer = ("Here are my lessons.\n**LESSON 1:** Check every capture before moving.\n"
              "Lesson: Keep the king safe.\nLESSON: third\nLESSON: fourth")
    got = nb.read_lessons(answer, 3)
    check(got == ["Check every capture before moving.", "Keep the king safe.", "third"],
          f"decorated lines read, and at most 3 kept ({got})")
    check(nb.read_lessons("I have no lessons.", 3) == [], "an answer without LESSON lines gives none")

    with tempfile.TemporaryDirectory() as tmp:
        book = nb.Notebook(Path(tmp) / "notebook")
        book.save(["Look at every check and capture first."], "start")

        print("\n2. What Magnus and Hans are sent")
        magnus = PretendClaude([], name="Magnus", notebook_path=book.path)
        hans = PretendClaude([], name="Hans")
        board = chess.Board()
        m_msg, h_msg = magnus.turn_message(Turn(board, "white")), hans.turn_message(Turn(board, "white"))
        check("1. Look at every check and capture first." in m_msg and "#" not in m_msg,
              "Magnus's message contains his notebook (without the heading)")
        check("notebook" not in h_msg.lower(), "Hans's message has no notebook")
        check(m_msg.replace(m_msg[m_msg.index("\nYour notebook"):m_msg.index("\nReply")], "") == h_msg,
              "apart from the notebook, both messages are identical")

        print("\n3. Colours swap; a stopped game is continued")
        check(next_game([]) == (1, True, None), "game 1: Magnus is White")
        check(next_game([fake_game(1, True, "1-0")]) == (2, False, None), "game 2: Magnus is Black")
        check(next_game([fake_game(1, True, "1-0"), fake_game(2, False, "0-1")]) == (3, True, None),
              "game 3: Magnus is White again")
        stopped = fake_game(2, False, "*")
        check(next_game([fake_game(1, True, "1-0"), stopped]) == (2, False, stopped["id"]),
              "a stopped game 2 is continued with the same colours")
        check(not needs_lessons(fake_game(1, True, "1-0")), "no lessons after Magnus wins")
        check(needs_lessons(fake_game(1, True, "0-1")) and needs_lessons(fake_game(1, False, "1/2-1/2")),
              "lessons after Magnus loses or draws")
        check(not needs_lessons(stopped), "no lessons for an unfinished game")

        print("\n4. A practice game Magnus does not win (random moves stand in for Claude)")
        games = Path(tmp) / "games"
        games.mkdir()
        d = play_game(RandomPlayer("Magnus", seed=11), RandomPlayer("Hans", seed=12), "match-01", "practice",
                      kind="match", games_dir=games, move_limit=40, seed=1, log=lambda *a, **k: None)
        from review import review_diary
        from stockfish import open_engine
        engine = open_engine()
        try:
            review_diary(d, engine)
        finally:
            engine.quit()
        check(needs_lessons(d), f"Magnus did not win ({d['result_text']}), so lessons are due")
        writer = PretendClaude(["LESSON: Before every move, list what my opponent threatens.\n"
                                "LESSON: Do not grab pawns while my king is unsafe.\n"
                                "LESSON: Count attackers and defenders before exchanging."],
                               name="Magnus", notebook_path=book.path)
        record = nb.write_lessons(d, "white", writer, book)
        sent = writer.messages[0]
        worst = nb.worst_moves(d, "white")
        check(len(worst) == 3 and all(f"{m['move_number']}. {m['san']}" in sent for m in worst),
              f"he is shown his 3 worst moves ({', '.join(m['san'] for m in worst)})")
        check("Stockfish preferred" in sent and "What you thought at the time" in sent,
              "each with Stockfish's better move and his own thought at the time")
        check("1. Look at every check and capture first." in sent, "and his current notebook")
        check(len(book.lessons()) == 4 and record["new_lessons"][0].startswith("Before every move"),
              f"3 new lessons added: the notebook now has {len(book.lessons())}")
        archive = [json.loads(line) for line in book.archive.read_text(encoding="utf-8").splitlines()]
        check(len(archive) == 3 and all(a["game"] == "match-01" for a in archive),
              "the archive records the 3 lessons and their game")
        check((book.history / record["copy"]).exists(), f"a dated copy was saved ({record['copy']})")

        print("\n5. A full notebook is merged down")
        book.save([f"Old lesson {i}." for i in range(1, nb.NOTEBOOK_CAP)], "nearly-full")
        merged_reply = "\n".join(f"LESSON: Merged lesson {i}." for i in range(1, nb.MERGE_TARGET + 1))
        writer = PretendClaude(["LESSON: New A.\nLESSON: New B.\nLESSON: New C.", merged_reply],
                               name="Magnus", notebook_path=book.path)
        record = nb.write_lessons(d, "white", writer, book)
        check(record["merged"] and len(writer.messages) == 2,
              f"{nb.NOTEBOOK_CAP - 1} + 3 lessons is over the cap of {nb.NOTEBOOK_CAP}: one extra request merges them")
        check(f"at most {nb.MERGE_TARGET}" in writer.messages[1] and "Old lesson 14." in writer.messages[1],
              "the merge request shows all lessons and the target size")
        check(book.lessons() == [f"Merged lesson {i}." for i in range(1, nb.MERGE_TARGET + 1)],
              f"the notebook now holds the {nb.MERGE_TARGET} merged lessons")
        archive = book.archive.read_text(encoding="utf-8")
        check(archive.count("\n") == 6 and "New C." in archive, "the archive still keeps every lesson written")
        check(len(list(book.history.glob("*.md"))) == 4, "every change left a dated copy")

    print(f"\n{'ALL CHECKS PASSED' if failures == 0 else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
