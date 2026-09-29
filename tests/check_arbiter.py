"""
Automatic checks for the arbiter (Phase 6). No AI is used; costs nothing.

1. Tricky suggestions are judged correctly (illegal ones refused).
2. Every way a game can end is recognised.
3. Players get up to 3 tries; after that the arbiter plays a marked random move.
4. 20 full random games finish, every diary is re-checked move by move,
   and the real website replays them all with the board matching.

Run:  python tests/check_arbiter.py
"""

import sys
import tempfile
from pathlib import Path

import chess

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "arena"))
sys.path.insert(0, str(ROOT / "tests"))
from arbiter import MAX_ATTEMPTS, play_game, read_move  # noqa: E402
from browser_harness import run_page  # noqa: E402
from check_diaries import check_diary  # noqa: E402
from players import RandomPlayer, ScriptedPlayer, SloppyPlayer  # noqa: E402

failures = 0


def check(ok: bool, text: str) -> None:
    global failures
    print(f"{'PASS' if ok else 'FAIL'}  {text}")
    failures += not ok


START = chess.STARTING_FEN
# (position, suggestion, expected move in computer notation, or None = must be refused)
MOVE_CASES = [
    (START, "e4", "e2e4", "normal pawn move"),
    (START, "e2e4", "e2e4", "computer notation"),
    (START, "Nf3!", "g1f3", "move with a '!' comment"),
    (START, "g1f3", "g1f3", "computer notation for a knight"),
    (START, "e5", None, "a square White's pawns cannot reach"),
    (START, "Ke2", None, "king blocked by its own pawn"),
    (START, "O-O", None, "castling with pieces in the way"),
    (START, "banana", None, "nonsense text"),
    (START, "", None, "no move at all"),
    (START, "e4 e5", None, "two moves at once"),
    ("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1", "Kf2", None, "king walking into check"),
    ("4k3/8/8/8/8/8/4r3/4K3 w - - 0 1", "Kxe2", "e1e2", "king capturing an undefended rook"),
    ("4k3/8/8/8/8/8/5r2/R3K2R w KQ - 0 1", "O-O", None, "castling through an attacked square"),
    ("4k3/8/8/8/8/8/5r2/R3K2R w KQ - 0 1", "0-0-0", "e1c1", "castling written with zeros"),
    ("4k3/4r3/8/8/8/8/4N3/4K3 w - - 0 1", "Nc3", None, "moving a pinned knight"),
    ("4k3/8/8/8/8/8/8/1N2KN2 w - - 0 1", "Nd2", None, "ambiguous: two knights can go to d2"),
    ("4k3/8/8/8/8/8/8/1N2KN2 w - - 0 1", "Nbd2", "b1d2", "ambiguity resolved: Nbd2"),
    ("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a8=Q", "a7a8q", "promotion to a queen"),
    ("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a8=N", "a7a8n", "promotion to a knight"),
    ("4k3/P7/8/8/8/8/8/4K3 w - - 0 1", "a7a8", "a7a8q", "promotion without a piece becomes a queen"),
    ("4k3/8/8/3pP3/8/8/8/4K3 w - d6 0 1", "exd6", "e5d6", "en passant"),
    ("4k3/8/8/3pP3/8/8/8/4K3 w - - 0 1", "exd6", None, "en passant no longer allowed"),
]

# (name, start position, White's moves, Black's moves, expected ending, move limit)
ENDING_CASES = [
    ("checkmate (Fool's mate)", START, ["f3", "g4"], ["e5", "Qh4#"], ("0-1", "checkmate"), 60),
    ("stalemate", "7k/8/5QK1/8/8/8/8/8 w - - 0 1", ["Qf7"], [], ("1/2-1/2", "stalemate"), 60),
    ("not enough pieces", "4k3/8/8/8/8/8/3p4/4K3 w - - 0 1", ["Kxd2"], [], ("1/2-1/2", "insufficient_material"), 60),
    ("threefold repetition", START, ["Nf3", "Ng1", "Nf3", "Ng1"], ["Nf6", "Ng8", "Nf6", "Ng8"],
     ("1/2-1/2", "repetition"), 60),
    ("50-move rule", "4k3/8/8/8/8/8/8/R3K3 w - - 99 30", ["Ra2"], [], ("1/2-1/2", "fifty_moves"), 60),
]


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    quiet = lambda *a: None  # noqa: E731

    print("1. Judging suggested moves")
    for fen, text, expected, label in MOVE_CASES:
        move, reason = read_move(chess.Board(fen), text)
        got = move.uci() if move else None
        note = f"accepted as {got}" if got else f"refused: {reason}"
        check(got == expected, f"{label} ('{text}') -> {note}")

    with tempfile.TemporaryDirectory() as tmp:
        games = Path(tmp)

        print("\n2. Every way a game can end")
        for name, fen, w, b, expected, limit in ENDING_CASES:
            d = play_game(ScriptedPlayer(w), ScriptedPlayer(b), "ending", name,
                          games_dir=games, start_fen=fen, move_limit=limit, log=quiet)
            check((d["result"], d["termination"]) == expected,
                  f"{name}: {d['result_text']} [{d['result']}]")
        d = play_game(RandomPlayer(seed=1), RandomPlayer(seed=2), "ending", "move limit",
                      games_dir=games, move_limit=5, log=quiet)
        check(d["termination"] == "move_limit" and len(d["moves"]) == 10,
              f"move limit of 5 moves each: {d['result_text']} after {len(d['moves'])} half-moves")

        print("\n3. Retries and the arbiter's fallback move")
        d = play_game(SloppyPlayer("Sloppy", seed=7), RandomPlayer(seed=8), "sloppy",
                      "sloppy", games_dir=games, move_limit=20, seed=3, log=quiet)
        retried = [m for m in d["moves"] if m["illegal_attempts"]]
        check(len(retried) > 5 and all(m["color"] == "white" for m in retried),
              f"sloppy player's illegal tries were refused and retried ({len(retried)} moves needed retries)")
        check(not any(m.get("fallback") for m in d["moves"]),
              "a player that gets it right within 3 tries never needs the fallback")
        hopeless = ScriptedPlayer(["xx", "Ke9", "banana"] + ["e4"] * 5, name="Hopeless")
        d = play_game(hopeless, RandomPlayer(seed=9), "hopeless", "hopeless",
                      games_dir=games, move_limit=2, seed=4, log=quiet)
        first = d["moves"][0]
        check(first.get("fallback") is True and first["illegal_attempts"] == MAX_ATTEMPTS
              and first["illegal_suggestions"] == ["xx", "Ke9", "banana"],
              f"after {MAX_ATTEMPTS} failed tries the arbiter plays a marked random move ({first['san']})")
        for f in games.glob("*.json"):
            f.unlink()

        print("\n4. Twenty full random games")
        for i in range(1, 21):
            play_game(RandomPlayer("Random A", seed=100 + i), RandomPlayer("Random B", seed=200 + i),
                      f"random-{i:02d}", f"Random game {i}", games_dir=games, seed=i, log=quiet)
        diaries = sorted(p for p in games.glob("random-*.json"))
        bad = [p.name for p in diaries if check_diary(p)]
        check(len(diaries) == 20 and not bad,
              f"20 games finished and every diary re-checks move by move{' (bad: ' + ', '.join(bad) + ')' if bad else ''}")
        import json
        endings = {}
        for p in diaries:
            t = json.loads(p.read_text(encoding="utf-8"))["termination"]
            endings[t] = endings.get(t, 0) + 1
        print(f"      endings: {endings}")
        print("      replaying all 20 games in the website (hidden browser)...")
        result = run_page("/__tests/selftest.html", games_dir=games)
        passed_games = sum(1 for line in result.splitlines() if line.startswith("PASS "))
        check("ALL GAMES PASSED" in result and passed_games == 20,
              f"the website replays all 20 games with the board matching every move ({passed_games} passed)")

    print(f"\n{'ALL CHECKS PASSED' if failures == 0 else f'{failures} CHECK(S) FAILED'}")
    return 1 if failures else 0


if __name__ == "__main__":
    sys.exit(main())
