"""
Automatic checks for Magnus's learning material and the experiment (version 2).
No real Claude requests: a pretend Claude gives prepared answers. Costs nothing.
Needs Stockfish in engines/ (to grade the practice game and score puzzles).

1. Notebook rules are read correctly from Claude's answers.
2. What Magnus and Hans are sent: the only differences are the learning material
   (notebook, mistake library) and the notebook step of the move protocol.
3. The game phase, used to choose similar past mistakes.
4. The opening book: legal, played for both sides, then the players take over;
   book moves are not counted in the grades.
5. The experiment's schedule (puzzle tests, Stockfish games, openings, colours).
6. After a practice game: refutations, the mistake library, and a notebook rewrite.
7. The puzzle test is scored with Stockfish.

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

import experiment as exp  # noqa: E402
import notebook as nb  # noqa: E402
import openings  # noqa: E402
import puzzles  # noqa: E402
from arbiter import play_game  # noqa: E402
from check_agent import PretendClaude  # noqa: E402
from play import needs_lessons  # noqa: E402
from players import RandomPlayer, Turn  # noqa: E402
from review import review_diary  # noqa: E402
from stockfish import open_engine  # noqa: E402

failures = 0


def check(ok: bool, text: str) -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'}  {text}")
    failures += not ok


def fake_game(number: int, magnus_white: bool, result: str) -> dict:
    names = ("Magnus", "Hans") if magnus_white else ("Hans", "Magnus")
    return {"id": f"2026-10-01-1200-match-{number:02d}", "kind": "match", "result": result,
            "winner": {"1-0": "white", "0-1": "black"}.get(result),
            "white": {"name": names[0]}, "black": {"name": names[1]}}


def fake_checkpoint(key: str, result: str = "0-1") -> dict:
    return {"id": f"2026-10-01-1200-{key}", "kind": "yardstick", "result": result}


def strip_between(text: str, start: str, end: str) -> str:
    """Removes the part of `text` from `start` up to (not including) `end`."""
    if start not in text:
        return text
    i = text.index(start)
    return text[:i] + text[text.index(end, i):]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")

    print("1. Reading notebook rules from Claude's answers")
    answer = ("Here is my notebook.\n**LESSON 1:** middlegame | Count the defenders before taking a pawn. | Qxd6 lost my queen.\n"
              "Lesson: Endgame | Keep my king near passed pawns. | Kf3 let the pawn run.\n"
              "LESSON: middlegame | Count the defenders before taking a pawn. | Qxd6 lost my queen.\n"
              "LESSON: Plain rule without a phase.")
    got = nb.read_lessons(answer, 15)
    check(got == ["[middlegame] Count the defenders before taking a pawn. Example: Qxd6 lost my queen.",
                  "[endgame] Keep my king near passed pawns. Example: Kf3 let the pawn run.",
                  "Plain rule without a phase."], f"phase, rule and example read; the duplicate dropped ({len(got)} rules)")
    check(len(nb.read_lessons("\n".join(f"LESSON: opening | rule {i} | ex" for i in range(20)), 15)) == 15,
          "at most 15 rules are kept")
    check(nb.read_lessons("I have no lessons.", 15) == [], "an answer without LESSON lines gives none")

    with tempfile.TemporaryDirectory() as tmp:
        book = nb.Notebook(Path(tmp) / "notebook")
        book.save(["[opening] Look at every check and capture first."], "start")
        library = nb.MistakeLibrary(Path(tmp) / "notebook" / "mistakes.jsonl")

        print("\n2. What Magnus and Hans are sent")
        import play
        library.path.write_text(json.dumps(play.SAMPLE_MISTAKE) + "\n", encoding="utf-8")
        magnus = PretendClaude([], name="Magnus", notebook_path=book.path, mistakes=library, learner=True)
        hans = PretendClaude([], name="Hans", learner=False)
        board = chess.Board()
        m_msg, h_msg = magnus.turn_message(Turn(board, "white")), hans.turn_message(Turn(board, "white"))
        check("1. [opening] Look at every check and capture first." in m_msg and nb.HEADING not in m_msg,
              "Magnus's message contains his notebook (without the heading)")
        check("Your own past mistakes" in m_msg and "Nxe5" in m_msg and "How it was punished" in m_msg,
              "and a similar past mistake from his library, with how it was punished")
        check("1. Read your notebook" in m_msg and "RULES:" in m_msg, "his protocol starts with reading the notebook")
        check("notebook" not in h_msg.lower() and "mistake" not in h_msg.lower() and "RULES" not in h_msg,
              "Hans's message has no notebook, no mistake library and no notebook step")
        learning = strip_between(strip_between(m_msg, "\nYour notebook", "\nYour own"), "\nYour own", "\nHow to")
        check(strip_between(learning, "How to choose", "MOVE: <one") ==
              strip_between(h_msg, "How to choose", "MOVE: <one"),
              "apart from the learning material and the protocol, both messages are identical")
        check("Calculate at least 2 candidate moves" in m_msg and "Calculate at least 2 candidate moves" in h_msg,
              "both must calculate at least 2 candidate moves")

        print("\n3. The game phase")
        check(nb.game_phase(chess.Board()) == "opening", "the start position is the opening")
        middle = chess.Board("r1bq1rk1/pp2bppp/2n1pn2/3p4/3P4/2NBPN2/PP3PPP/R2QK2R w KQ - 0 20")
        check(nb.game_phase(middle) == "middlegame", "move 20 with queens and most pieces is the middlegame")
        check(nb.game_phase(chess.Board("8/5k2/8/8/8/8/3R1K2/8 w - - 0 40")) == "endgame",
              "rook and king against king is the endgame")

        print("\n4. The opening book")
        check(openings.check_book() == [], f"all {len(openings.OPENINGS)} openings are legal")
        check(len({o['name'] for o in openings.OPENINGS}) == 10 and all(
            o["name"] in {x["name"] for x in openings.OPENINGS} for o in map(openings.by_name,
                                                                                openings.CHECKPOINT_OPENINGS.values())),
              "10 different openings; the checkpoint openings are among them")
        french = openings.by_name("French Defence")
        games = Path(tmp) / "games"
        games.mkdir()
        d = play_game(openings.OpeningBook(RandomPlayer("Magnus", seed=11), french),
                      openings.OpeningBook(RandomPlayer("Hans", seed=12), french), "match-01", "practice",
                      kind="match", games_dir=games, move_limit=40, seed=1, log=lambda *a, **k: None)
        sans = [m["san"] for m in d["moves"]]
        check(sans[:6] == openings.book_moves(french) and all(m["thought_source"] == "book" for m in d["moves"][:6])
              and d["moves"][6]["thought_source"] != "book",
              "the book's 6 moves are played, then the players take over")
        engine = open_engine()
        try:
            review_diary(d, engine)
            again = json.loads(json.dumps(d))
            for m in again["moves"][:6]:
                m["thought_source"] = "move_description"
            review_diary(again, engine)
            check(d["review"]["white"] != again["review"]["white"] and "review" in d["moves"][0],
                  "book moves are graded but not counted in the players' accuracy")

            print("\n5. The experiment's schedule")
            steps = exp.schedule()
            keys = [s["key"] for s in steps]
            check(not exp.PUZZLE_TEST and len(steps) == 24
                  and keys[:4] == ["checkpoint-00-magnus-white", "checkpoint-00-magnus-black",
                                   "checkpoint-00-hans-white", "checkpoint-00-hans-black"],
                  "24 games (the puzzle test is switched off), starting with checkpoint 0: 4 Stockfish games")
            match = [s for s in steps if s["kind"] == "match"]
            check(keys[4] == "match-01" and keys[9] == "match-06" and keys[10] == "checkpoint-06-magnus-white"
                  and keys[-5] == "match-12", "checkpoint 6 comes after game 6, checkpoint 12 after game 12")
            check([s["magnus_white"] for s in match[:4]] == [True, False, True, False]
                  and match[0]["opening"] == match[1]["opening"] != match[2]["opening"]
                  and len({s["opening"] for s in match}) == 6,
                  "each opening is played twice, with the colours swapped (6 openings for 12 games)")
            nothing_done = lambda step: False  # noqa: E731
            all_done = lambda step: True  # noqa: E731
            check(exp.next_step([], nothing_done)[0]["key"] == "checkpoint-00-magnus-white",
                  "nothing played: checkpoint 0 first")
            checkpoint0 = [fake_checkpoint(k) for k in keys[:4]]
            check(exp.next_step(checkpoint0, all_done)[0]["key"] == "match-01", "after checkpoint 0: game 1")
            stopped = fake_game(2, False, "*")
            check(exp.next_step(checkpoint0 + [fake_game(1, True, "1-0"), stopped], all_done) == (steps[5], stopped),
                  "a stopped game 2 is continued")
            check(needs_lessons(fake_game(1, True, "1-0")) and needs_lessons(fake_game(1, False, "1/2-1/2"))
                  and not needs_lessons(stopped), "Magnus studies every finished game, wins included")
            check(exp.main_model(["claude-haiku-4-5", "claude-opus-5-5"], "opus") == "claude-opus-5-5",
                  "the exact model behind the 'opus' shortcut is recognised")

            print("\n6. After a practice game: refutations, the mistake library, a notebook rewrite")
            nb.add_refutations(d, "white", engine)
            worst = nb.worst_moves(d, "white")
            check(len(worst) == 3 and all(m["thought_source"] != "book" for m in worst)
                  and all(m["review"].get("refutation") for m in worst),
                  f"his 3 worst moves (not book moves), each with how it was punished "
                  f"({', '.join(m['san'] + ': ' + m['review']['refutation'][:20] for m in worst)})")
            library.path.unlink()
            added = library.add_game(d, "white")
            expected = sum(1 for m in d["moves"] if m["color"] == "white" and m["thought_source"] != "book"
                           and m["review"]["label"] in nb.LIBRARY_LABELS)
            check(added == expected > 0 and library.add_game(d, "white") == 0,
                  f"his {added} mistakes and blunders go into the library, never twice")
            entry = library.entries()[0]
            board = chess.Board(entry["fen"])
            check(library.similar(board, "white")[0]["fen"] == entry["fen"]
                  and all(e["phase"] == entry["phase"] for e in library.similar(board, "white")),
                  "the most similar past mistake to a position is the one made there; same phase only")
            reply = ("LESSON: middlegame | Count defenders before capturing. | Qxd6 lost the queen.\n"
                     "LESSON: middlegame | Count defenders before capturing. | Qxd6 lost the queen.\n"
                     "LESSON: endgame | Keep the king close to passed pawns. | Kf3 was too slow.")
            writer = PretendClaude([reply], name="Magnus", notebook_path=book.path, learner=True)
            record = nb.write_lessons(d, "white", writer, book)
            sent = writer.messages[0]
            check(all(f"{m['move_number']}. {m['san']}" in sent for m in worst)
                  and "Stockfish preferred" in sent and "How it was punished" in sent
                  and "What you thought at the time" in sent and "Look at every check" in sent,
                  "he is shown his worst moves, better moves, punishments, his thoughts and his notebook")
            check(len(book.lessons()) == 2 and record["dropped"] == 1 and record["notebook_size"] == 2,
                  "the rewrite replaces the notebook: 2 rules (the duplicate merged, the old rule dropped)")
            archive = [json.loads(line) for line in book.archive.read_text(encoding="utf-8").splitlines()]
            check(len(archive) == 2 and all(a["game"] == "match-01" for a in archive),
                  "the archive records the new rules and their game")
            check((book.history / record["copy"]).exists(), f"a dated copy was saved ({record['copy']})")
            writer = PretendClaude(["\n".join(f"LESSON: opening | Rule {i}. | ex" for i in range(20))],
                                   name="Magnus", notebook_path=book.path, learner=True)
            nb.write_lessons(d, "white", writer, book)
            check(len(book.lessons()) == nb.NOTEBOOK_CAP, f"a rewrite never holds more than {nb.NOTEBOOK_CAP} rules")

            print("\n7. The puzzle test is scored with Stockfish")
            mate_in_one = "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 2 3"
            puzzles.PUZZLE_SET = Path(tmp) / "puzzle_set.json"
            puzzles.RESULTS_DIR = Path(tmp) / "data"
            puzzles.PUZZLE_SET.write_text(json.dumps({"puzzles": [
                {"id": "p01", "start_fen": mate_in_one, "moves": [], "color": "white"},
                {"id": "p02", "start_fen": mate_in_one, "moves": [], "color": "white"}]}), encoding="utf-8")
            step = {"checkpoint": 0, "agent": "hans", "kind": "puzzles"}
            solver = PretendClaude(["THOUGHT: Mate.\nMOVE: Qxf7#", "THOUGHT: A quiet move.\nMOVE: a3"],
                                   name="Hans", learner=False)
            check(puzzles.run(step, solver, engine, log=lambda *a: None) and puzzles.done(step),
                  "both puzzles are answered and saved")
            s = puzzles.summary(step)
            answers = puzzles.load_results(step)["answers"]
            check(answers["p01"]["accuracy"] == 100 and answers["p02"]["label"] == "blunder"
                  and s["best_found"] == 1 and s["blunders"] == 1,
                  f"mate scores 100, missing it is a blunder (score {s['score']}%)")
        finally:
            engine.quit()

    print(f"\n{'ALL CHECKS PASSED' if failures == 0 else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
