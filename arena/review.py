"""
Game review: grades every move with full-strength Stockfish, like chess.com's
"Accuracy". Free: no Claude requests.

For each move we compare the mover's chance of winning before and after it.
A move that keeps the chances scores near 100%; one that throws them away
scores near 0%. We use Lichess's published formulas (chess.com's are secret).

Saved into each diary:
- per move:  "review": {eval_cp, win_before, win_after, accuracy, label}
- per game:  "review": {engine, depth, white: {...}, black: {...}}
  with accuracy %, average centipawn loss (a centipawn is 1/100 of a pawn),
  and counts of inaccuracies, mistakes and blunders.

Run:  python arena/review.py                      (every game in docs/games)
      python arena/review.py docs/games/xyz.json  (just these)
"""

import json
import math
import statistics
import sys
from pathlib import Path

import chess
import chess.engine

import diary
from stockfish import open_engine

DEPTH = 16          # how many half-moves ahead Stockfish looks for each position
CP_CAP = 1000       # evaluations are capped at +/-10 pawns (Lichess does the same)

# Drop in the mover's winning chances (percentage points) for each label.
LABELS = [(15, "blunder"), (10, "mistake"), (5, "inaccuracy")]


def win_percent(cp: float) -> float:
    """Chance of winning (0-100) for a side that is `cp` centipawns ahead."""
    cp = max(-CP_CAP, min(CP_CAP, cp))
    return 50 + 50 * (2 / (1 + math.exp(-0.00368208 * cp)) - 1)


def move_accuracy(win_before: float, win_after: float) -> float:
    """Lichess's accuracy of one move, from the mover's winning chances."""
    if win_after >= win_before:
        return 100.0
    raw = 103.1668100711649 * math.exp(-0.04354415386753951 * (win_before - win_after)) - 3.166924740191411
    return max(0.0, min(100.0, raw + 1))  # +1: Lichess's allowance for engine uncertainty


def white_cp(score: chess.engine.PovScore) -> int:
    """An evaluation in centipawns from White's side (checkmates count as +/-10 pawns)."""
    return max(-CP_CAP, min(CP_CAP, score.white().score(mate_score=100_000)))


def game_accuracy(accuracies: list[float], weights: list[float]) -> float:
    """Lichess's game accuracy: the average of a volatility-weighted mean and a
    harmonic mean (which punishes a few very bad moves more strongly)."""
    if not accuracies:
        return 0.0
    weighted = sum(a * w for a, w in zip(accuracies, weights)) / sum(weights)
    harmonic = len(accuracies) / sum(1 / max(a, 1.0) for a in accuracies)
    return (weighted + harmonic) / 2


def volatility_weights(wins: list[float]) -> list[float]:
    """How 'sharp' the game was around each move (Lichess's sliding windows)."""
    n_moves = len(wins) - 1
    size = max(2, min(8, len(wins) // 10))
    windows = [wins[:size]] * max(0, size - 2) + [wins[i:i + size] for i in range(len(wins) - size + 1)]
    weights = [max(0.5, min(12.0, statistics.pstdev(w))) for w in windows]
    weights += [weights[-1]] * (n_moves - len(weights))
    return weights[:n_moves]


def review_diary(d: dict, engine: chess.engine.SimpleEngine, depth: int = DEPTH) -> dict:
    """Grades every move of a diary (changes it in place) and returns the summary."""
    # Same grades every time: one thread, and a fresh start for each game, so
    # Stockfish's memory of earlier games (its "hash table") cannot change them.
    engine.configure({"Threads": 1})
    # (A new `game` label makes python-chess tell Stockfish "new game".)
    limit, game = chess.engine.Limit(depth=depth), object()

    def evaluate(board: chess.Board) -> int:
        return white_cp(engine.analyse(board, limit, game=game)["score"])

    board = chess.Board(d["start_fen"])
    evals = [evaluate(board)]
    for m in d["moves"]:
        board.push_uci(m["uci"])
        if board.is_checkmate():
            evals.append(CP_CAP if board.turn == chess.BLACK else -CP_CAP)
        elif board.is_game_over():
            evals.append(0)
        else:
            evals.append(evaluate(board))

    white_wins = [win_percent(cp) for cp in evals]
    weights = volatility_weights(white_wins)
    per_side = {"white": {"acc": [], "w": [], "loss": [], "labels": []},
                "black": {"acc": [], "w": [], "loss": [], "labels": []}}

    for i, m in enumerate(d["moves"]):
        sign = 1 if m["color"] == "white" else -1
        before, after = win_percent(sign * evals[i]), win_percent(sign * evals[i + 1])
        acc = move_accuracy(before, after)
        drop = before - after
        label = next((name for limit, name in LABELS if drop >= limit), None)
        m["review"] = {"eval_cp": evals[i + 1], "win_before": round(before, 1),
                       "win_after": round(after, 1), "accuracy": round(acc, 1), "label": label}
        side = per_side[m["color"]]
        side["acc"].append(acc)
        side["w"].append(weights[i])
        side["loss"].append(max(0, sign * (evals[i] - evals[i + 1])))
        side["labels"].append(label)

    summary = {"engine": engine.id.get("name"), "depth": depth}
    for color, s in per_side.items():
        summary[color] = {
            "accuracy": round(game_accuracy(s["acc"], s["w"]), 1),
            "acpl": round(sum(s["loss"]) / len(s["loss"])) if s["loss"] else 0,
            "inaccuracies": s["labels"].count("inaccuracy"),
            "mistakes": s["labels"].count("mistake"),
            "blunders": s["labels"].count("blunder"),
        }
    d["review"] = summary
    return summary


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    paths = [Path(p) for p in sys.argv[1:]] or sorted(
        p for p in diary.GAMES_DIR.glob("*.json") if p.name != "index.json")
    engine = open_engine()
    try:
        for path in paths:
            d = json.loads(path.read_text(encoding="utf-8"))
            if not d["moves"]:
                continue
            s = review_diary(d, engine)
            path.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
            print(f"\n{d['title']}  ({d['result_text']})")
            for color in ("white", "black"):
                r = s[color]
                print(f"  {d[color]['name']:<22} accuracy {r['accuracy']:5.1f}%   avg loss {r['acpl']:4d} cp   "
                      f"{r['inaccuracies']} inaccuracies, {r['mistakes']} mistakes, {r['blunders']} blunders")
            worst = sorted((m for m in d["moves"] if m["review"]["label"] == "blunder"),
                           key=lambda m: m["review"]["win_after"] - m["review"]["win_before"])[:4]
            for m in worst:
                dots = "." if m["color"] == "white" else "..."
                print(f"     blunder {m['move_number']}{dots} {m['san']:<7} chances "
                      f"{m['review']['win_before']:.0f}% -> {m['review']['win_after']:.0f}%")
    finally:
        engine.quit()
    return 0


if __name__ == "__main__":
    sys.exit(main())
