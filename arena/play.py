"""
Runs games with the Claude agent. Uses your Claude Pro plan (never the paid API).

  python arena/play.py test-moves          5 single moves from different positions
  python arena/play.py game                one full Claude vs Claude game
  python arena/play.py game --resume ID    continue a game that stopped
  python arena/play.py yardstick           Claude vs Stockfish at its weakest (--agent-color, --skill)

Options for "game":  --model sonnet|haiku  --effort low|medium|high  --limit N (0 = none, the default)
"""

import argparse
import sys
import time
from datetime import datetime

import chess

import arbiter
import diary
from claude_agent import AgentUnavailable, ClaudeAgent, check_no_paid_api
from players import Turn

# Positions for the single-move test: (description, position, what a good answer looks like)
TEST_POSITIONS = [
    ("Opening move for White", chess.STARTING_FEN, "any sensible opening move"),
    ("Black replies to 1. e4", "rnbqkbnr/pppppppp/8/8/4P3/8/PPPP1PPP/RNBQKBNR b KQkq - 0 1",
     "e.g. e5, c5, e6"),
    ("White can checkmate in one", "r1bqkbnr/pppp1ppp/2n5/4p2Q/2B1P3/8/PPPP1PPP/RNB1K1NR w KQkq - 2 3",
     "Qxf7#"),
    ("Black's queen is attacked by the knight", "rnb1kbnr/pppp1ppp/8/4p3/4P2q/5N2/PPPP1PPP/RNBQKB1R b KQkq - 0 3",
     "Qxe4+ (takes a pawn with check) or moving the queen to safety"),
    ("White pawn can promote", "8/P5k1/8/8/8/8/6K1/8 w - - 0 1", "a8=Q"),
]


def usage_text(u: dict | None) -> str:
    if not u:
        return ""
    return f"[{u['input_tokens']} in / {u['output_tokens']} out, {u['seconds']}s]"


def test_moves(args) -> int:
    agent = ClaudeAgent("Claude", model=args.model, effort=args.effort)
    agent.game_id = "single-move-test"
    legal_count = 0
    for i, (label, fen, good) in enumerate(TEST_POSITIONS, start=1):
        board = chess.Board(fen)
        color = "white" if board.turn == chess.WHITE else "black"
        print(f"\n{i}. {label} (hoping for: {good})")
        try:
            s = agent.suggest(Turn(board, color))
        except AgentUnavailable as err:
            print(f"   Stopped: {err}")
            return 1
        move, problem = arbiter.read_move(board, s.move_text)
        legal_count += bool(move)
        verdict = f"LEGAL -> {board.san(move)}" if move else f"REFUSED -> {problem}"
        print(f"   Claude said: MOVE {s.move_text!r}  {verdict}  {usage_text(agent.last_usage)}")
        print(f"   Thought: {s.thought}")
    print(f"\n{legal_count} of {len(TEST_POSITIONS)} suggestions were legal on the first try.")
    return 0


def play(args) -> int:
    engine_player = None
    if args.what == "yardstick":
        from stockfish import StockfishPlayer
        engine_player = StockfishPlayer(skill=args.skill)
        agent = ClaudeAgent(args.white_name, model=args.model, effort=args.effort)
        white, black = (agent, engine_player) if args.agent_color == "white" else (engine_player, agent)
        kind_label, notes = "vs-stockfish", f"Yardstick game: Claude vs Stockfish at skill {args.skill}."
    else:
        white = ClaudeAgent(args.white_name, model=args.model, effort=args.effort)
        black = ClaudeAgent(args.black_name, model=args.model, effort=args.effort)
        kind_label, notes = "claude-vs-claude", "Claude vs Claude test game. Both agents have no notebook."
    game_id = args.resume or f"{datetime.now():%Y-%m-%d-%H%M}-{kind_label}"
    title = f"{white.name} vs {black.name} ({args.model}, {datetime.now():%d %b %Y})"
    totals = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
    started = time.time()

    def show(m: dict) -> None:
        u = m.get("usage") or {}
        for key in totals:
            totals[key] += u.get(key, 0)
        dots = "." if m["color"] == "white" else "..."
        extra = f"  ({m['illegal_attempts']} refused)" if m["illegal_attempts"] else ""
        extra += "  ARBITER'S RANDOM MOVE" if m.get("fallback") else ""
        print(f"{m['move_number']}{dots} {m['san']:<8} {usage_text(u)}{extra}")
        print(f"      {m['thought']}")

    print(f"Game {game_id}: {white.name} (White) vs {black.name} (Black)")
    print(f"Model: {args.model}, effort: {args.effort}, "
          f"move limit: {args.limit or 'none (only the chess draw rules)'}\n")
    try:
        d = arbiter.play_game(white, black, game_id, title, kind="ai", move_limit=args.limit,
                              resume=bool(args.resume), on_move=show, notes=notes)
    except AgentUnavailable as err:
        diary.rebuild_index()
        print(f"\nThe game stopped: {err}")
        print("Everything so far is saved. To continue later, run:")
        print(f"   python arena/play.py {args.what} --resume {game_id}")
        return 1
    finally:
        if engine_player:
            engine_player.close()
    minutes = (time.time() - started) / 60
    print(f"\nResult: {d['result_text']} after {(len(d['moves']) + 1) // 2} moves")
    print(f"Claude requests: {totals['requests']}, text in: {totals['input_tokens']} tokens, "
          f"text out: {totals['output_tokens']} tokens, time: {minutes:.0f} minutes")
    print(f"Saved: docs/games/{game_id}.json")

    # Grade every move with full-strength Stockfish (free, about 15 seconds).
    import json
    from review import review_diary
    from stockfish import open_engine
    engine = open_engine()
    try:
        summary = review_diary(d, engine)
    finally:
        engine.quit()
    path = diary.GAMES_DIR / f"{game_id}.json"
    path.write_text(json.dumps(d, indent=2, ensure_ascii=False), encoding="utf-8")
    for color in ("white", "black"):
        r = summary[color]
        print(f"Accuracy {d[color]['name']}: {r['accuracy']}% "
              f"({r['inaccuracies']} inaccuracies, {r['mistakes']} mistakes, {r['blunders']} blunders)")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    check_no_paid_api()
    parser = argparse.ArgumentParser(description="Play chess with the Claude agent.")
    parser.add_argument("what", choices=["test-moves", "game", "yardstick"])
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--effort", default="low", choices=["low", "medium", "high"])
    parser.add_argument("--limit", type=int, default=0,
                        help="moves per side before a draw is declared (0 = no limit)")
    parser.add_argument("--resume", help="id of an unfinished game to continue")
    parser.add_argument("--white-name", default="Claude A")
    parser.add_argument("--black-name", default="Claude B")
    parser.add_argument("--agent-color", default="white", choices=["white", "black"],
                        help="yardstick: which colour Claude plays")
    parser.add_argument("--skill", type=int, default=0, help="yardstick: Stockfish skill level (0-20)")
    args = parser.parse_args()
    return test_moves(args) if args.what == "test-moves" else play(args)


if __name__ == "__main__":
    sys.exit(main())
