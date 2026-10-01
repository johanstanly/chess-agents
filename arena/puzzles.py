"""
The puzzle test: a fixed set of positions where a Claude player blundered in
version 1 of the experiment. Magnus and Hans each get every position as a
normal turn (Magnus with his notebook and mistake library), and Stockfish
scores the move they choose with the same Lichess formula as the game grades.

Much less luck than whole games: the same positions every time, so a rising
score means better moves, not easier opponents.

  python arena/puzzles.py build [games folder]   makes puzzles/puzzle_set.json (once)

The test itself is run by "python arena/play.py experiment" at each checkpoint.
Answers are saved after every puzzle, so a stopped test continues where it stopped.
"""

import hashlib
import json
import statistics
import sys
from pathlib import Path

import chess
import chess.engine

import arbiter
import diary
import review
from claude_agent import AgentUnavailable
from players import Turn

ROOT = Path(__file__).resolve().parent.parent
PUZZLE_SET = ROOT / "puzzles" / "puzzle_set.json"
RESULTS_DIR = ROOT / "docs" / "data"

SET_SIZE = 30
MIN_DROP = 20          # a position qualifies if the move played there lost this many winning-chance points


def build_set(games: list[dict], size: int = SET_SIZE) -> list[dict]:
    """Positions where a Claude player blundered, spread evenly over the games."""
    found = []
    for d in sorted(games, key=lambda d: d["id"]):
        moves = d["moves"]
        for i, m in enumerate(moves):
            r = m.get("review")
            if d[m["color"]].get("type") != "claude" or not r or m.get("thought_source") == "book":
                continue
            if r["win_before"] - r["win_after"] < MIN_DROP or m["san"] == r.get("best"):
                continue   # not a real mistake (the move played was Stockfish's choice)
            board = chess.Board(d["start_fen"])
            for earlier in moves[:i]:
                board.push_uci(earlier["uci"])
            if board.legal_moves.count() < 2:
                continue
            found.append({"source": f"{d['id']} move {m['move_number']}{'.' if m['color'] == 'white' else '...'}"
                                    f"{m['san']}", "start_fen": d["start_fen"],
                          "moves": [e["uci"] for e in moves[:i]], "color": m["color"],
                          "played_in_v1": m["san"], "best": r.get("best")})
    if len(found) > size:   # spread evenly over all the games
        found = [found[int(k * len(found) / size)] for k in range(size)]
    for k, p in enumerate(found, start=1):
        p["id"] = f"p{k:02d}"
    return found


def load_set() -> list[dict]:
    return json.loads(PUZZLE_SET.read_text(encoding="utf-8"))["puzzles"] if PUZZLE_SET.exists() else []


def fingerprint() -> str | None:
    return hashlib.sha256(PUZZLE_SET.read_bytes()).hexdigest()[:16] if PUZZLE_SET.exists() else None


def board_for(p: dict) -> chess.Board:
    board = chess.Board(p["start_fen"])
    for uci in p["moves"]:
        board.push_uci(uci)
    return board


# ---------- Results ----------

def result_path(step: dict) -> Path:
    return RESULTS_DIR / f"puzzles-{step['checkpoint']:02d}-{step['agent']}.json"


def load_results(step: dict) -> dict:
    path = result_path(step)
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    return {"checkpoint": step["checkpoint"], "agent": step["agent"].capitalize(), "answers": {}}


def done(step: dict) -> bool:
    puzzles = load_set()
    return bool(puzzles) and all(p["id"] in load_results(step)["answers"] for p in puzzles)


def summary(step: dict) -> dict | None:
    results = load_results(step)
    answers = list(results["answers"].values())
    if not answers:
        return None
    return {"checkpoint": step["checkpoint"], "agent": results["agent"], "answered": len(answers),
            "score": round(statistics.mean(a["accuracy"] for a in answers), 1),
            "best_found": sum(a["move"] == a["best"] for a in answers),
            "blunders": sum(a["label"] == "blunder" for a in answers),
            "mistakes": sum(a["label"] == "mistake" for a in answers),
            "rules_used": sum(bool(a.get("rules")) for a in answers)}


def mover_win(engine, board: chess.Board, mover: chess.Color, game) -> tuple[float, str | None]:
    """The mover's winning chances in this position (and Stockfish's best move, if any)."""
    if board.is_checkmate():
        return (0.0 if board.turn == mover else 100.0), None
    if board.is_game_over():
        return 50.0, None
    info = engine.analyse(board, chess.engine.Limit(depth=review.DEPTH), game=game)
    cp = review.white_cp(info["score"])
    best = board.san(info["pv"][0]) if info.get("pv") else None
    return review.win_percent(cp if mover == chess.WHITE else -cp), best


def run(step: dict, agent, engine: chess.engine.SimpleEngine, log=print) -> bool:
    """Gives the player every puzzle not yet answered. False if Claude stopped answering."""
    results = load_results(step)
    agent.game_id = f"puzzles-{step['checkpoint']:02d}"
    engine.configure({"Threads": 1})
    for p in load_set():
        if p["id"] in results["answers"]:
            continue
        board = board_for(p)
        feedback, move, suggestion = [], None, None
        try:
            for _ in range(arbiter.MAX_ATTEMPTS):
                suggestion = agent.suggest(Turn(board.copy(), p["color"], list(feedback)))
                move, problem = arbiter.read_move(board, suggestion.move_text)
                if move:
                    break
                feedback.append(problem)
        except AgentUnavailable as err:
            log(f"Stopped: {err}")
            return False
        game = object()   # a fresh start for Stockfish: the same scores every time
        mover = board.turn
        before, best = mover_win(engine, board, mover, game)
        if move:
            san = board.san(move)
            after_board = board.copy()
            after_board.push(move)
            after, _ = mover_win(engine, after_board, mover, game)
        else:
            san, after = "(no legal move)", 0.0
        accuracy = review.move_accuracy(before, after)
        label = next((name for limit, name in review.LABELS if before - after >= limit), None)
        results["answers"][p["id"]] = {
            "move": san, "best": best, "accuracy": round(accuracy, 1), "label": label,
            "win_before": round(before, 1), "win_after": round(after, 1),
            "thought": suggestion.thought if suggestion else "", "rules": (suggestion.extra if suggestion else {}).get("rules"),
            "illegal_attempts": len(feedback), "usage": agent.last_usage}
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        result_path(step).write_text(json.dumps(results, indent=2, ensure_ascii=False), encoding="utf-8")
        log(f"  {p['id']}  {san:<8} best {best or '-':<8} score {accuracy:5.1f}  {label or ''}")
    return True


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    if len(sys.argv) < 2 or sys.argv[1] != "build":
        print(__doc__)
        return 1
    folder = Path(sys.argv[2]) if len(sys.argv) > 2 else diary.GAMES_DIR
    games = [json.loads(f.read_text(encoding="utf-8")) for f in folder.glob("*.json") if f.name != "index.json"]
    puzzles = build_set(games)
    PUZZLE_SET.parent.mkdir(parents=True, exist_ok=True)
    PUZZLE_SET.write_text(json.dumps({"made_from": str(folder.relative_to(ROOT)), "min_drop": MIN_DROP,
                                      "puzzles": puzzles}, indent=2), encoding="utf-8")
    print(f"{len(puzzles)} puzzles saved to {PUZZLE_SET.relative_to(ROOT)}")
    for p in puzzles:
        print(f"  {p['id']}  {p['color']:5}  {p['source']}  (best: {p['best']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
