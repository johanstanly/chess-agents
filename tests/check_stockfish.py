"""
Automatic checks for Stockfish: the yardstick opponent and the move grades
(Phase 8). No AI is used; costs nothing. Needs Stockfish in engines/.

1. The grading formulas give sensible numbers.
2. Kasparov-Topalov 1999 is graded as a very accurate game, with Topalov's
   historic losing mistake 31...Kxa3 as the only blunder, and grading repeats exactly.
3. A Claude test game: 57. Qg7+ (threw the win away) is a blunder, and
   50. Qg5+ (gave up the queen but stayed clearly winning) is an inaccuracy.
4. The random-move player loses to the yardstick with either colour.
5. Every grade saved in docs/games is well formed.

Run:  python tests/check_stockfish.py
"""

import json
import sys
import tempfile
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "arena"))
sys.path.insert(0, str(ROOT / "tests"))
import diary  # noqa: E402
from arbiter import play_game  # noqa: E402
from check_diaries import check_diary  # noqa: E402
from players import RandomPlayer  # noqa: E402
from review import move_accuracy, review_diary, win_percent  # noqa: E402

failures = 0


def check(ok: bool, text: str) -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'}  {text}")
    failures += not ok


def load(name: str) -> dict:
    return json.loads((diary.GAMES_DIR / name).read_text(encoding="utf-8"))


def find(d: dict, number: int, color: str) -> dict:
    return next(m for m in d["moves"] if m["move_number"] == number and m["color"] == color)


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    try:
        from stockfish import StockfishPlayer, open_engine
        engine = open_engine()
    except SystemExit as err:
        print(f"SKIPPED  {err}")
        return 0

    try:
        print("1. Grading formulas")
        check(abs(win_percent(0) - 50) < 0.01, "an equal position is a 50% chance")
        check(win_percent(1000) > 95 and win_percent(-1000) < 5, "10 pawns ahead is almost a sure win")
        check(move_accuracy(60, 60) == 100, "a move that keeps the chances scores 100%")
        check(move_accuracy(75, 25) < 15, "a move that drops the chances by 50 points scores under 15%")

        print("\n2. Kasparov-Topalov 1999 (graded afresh)")
        d = load("sample-kasparov-topalov-1999.json")
        s = review_diary(d, engine)
        check(s["white"]["accuracy"] > 95 and s["white"]["blunders"] == 0,
              f"Kasparov: accuracy {s['white']['accuracy']}%, {s['white']['blunders']} blunders")
        blunders = [f"{m['move_number']}...{m['san']}" for m in d["moves"] if m["review"]["label"] == "blunder"]
        check(s["black"]["accuracy"] > 85 and blunders == ["31...Kxa3"],
              f"Topalov: accuracy {s['black']['accuracy']}%, only blunder {', '.join(blunders)} "
              f"(the historic losing mistake)")
        again = review_diary(load("sample-kasparov-topalov-1999.json"), engine)
        check(again == s, "grading the same game twice gives exactly the same grades")

        print("\n3. Claude test game of 29 Sep, 17:32 (graded afresh)")
        d = load("2026-09-29-1732-claude-vs-claude.json")
        review_diary(d, engine)
        qg7, qg5 = find(d, 57, "white"), find(d, 50, "white")
        check(qg7["san"] == "Qg7+" and qg7["review"]["label"] == "blunder",
              f"57. Qg7+ is a blunder (chances {qg7['review']['win_before']}% -> {qg7['review']['win_after']}%)")
        check(qg5["san"] == "Qg5+" and qg5["review"]["label"] == "inaccuracy",
              f"50. Qg5+ is an inaccuracy (still +{qg5['review']['eval_cp'] / 100:.1f} after it)")
    finally:
        engine.quit()

    print("\n4. Random player vs the yardstick (Stockfish at skill 0)")
    with tempfile.TemporaryDirectory() as tmp:
        games = Path(tmp)
        for i, random_color in enumerate(("white", "black")):
            rand = RandomPlayer("Random", seed=300 + i)
            fish = StockfishPlayer(skill=0)
            try:
                white, black = (rand, fish) if random_color == "white" else (fish, rand)
                d = play_game(white, black, f"yardstick-{i}", "Random vs yardstick",
                              games_dir=games, move_limit=0, seed=i, log=lambda *a, **k: None)
            finally:
                fish.close()
            fish_won = d["result"] == ("0-1" if random_color == "white" else "1-0")
            check(fish_won and not check_diary(games / f"yardstick-{i}.json"),
                  f"random player as {random_color}: {d['result_text']} after "
                  f"{(len(d['moves']) + 1) // 2} moves, diary re-checks")

    print("\n5. Saved grades in docs/games")
    labels = {None, "inaccuracy", "mistake", "blunder"}
    for path in sorted(p for p in diary.GAMES_DIR.glob("*.json") if p.name != "index.json"):
        d = json.loads(path.read_text(encoding="utf-8"))
        if not d["moves"]:
            continue
        bad = [m["ply"] for m in d["moves"]
               if "review" not in m or m["review"]["label"] not in labels
               or not 0 <= m["review"]["accuracy"] <= 100]
        ok_summary = "review" in d and all(0 <= d["review"][c]["accuracy"] <= 100 for c in ("white", "black"))
        check(not bad and ok_summary,
              f"{path.name}{' (bad half-moves: ' + str(bad[:5]) + ')' if bad else ''}")

    print(f"\n{'ALL CHECKS PASSED' if failures == 0 else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
