"""
Runs games with the Claude agent. Uses your Claude Pro plan (never the paid API).

  python arena/play.py test-moves          5 single moves from different positions
  python arena/play.py game                one full Claude vs Claude game
  python arena/play.py game --resume ID    continue a game that stopped
  python arena/play.py yardstick           Magnus (or --agent hans) vs Stockfish at its weakest
                                           (--agent-color white|black, --skill N)
  python arena/play.py experiment          THE EXPERIMENT: plays its next game (--games N for more)
  python arena/play.py dry-run             shows exactly what Magnus and Hans are sent (no Claude requests)
  python arena/play.py demo-live           a free practice game (random moves) to test the live view

The experiment (see experiment.py) is 20 Magnus vs Hans games plus checkpoints
(a puzzle test and Stockfish games), with settings locked by reset_experiment.py.
A stopped step (e.g. usage limit reached) continues automatically the next time
you run "experiment". Every finished game is graded by Stockfish; after every
Magnus vs Hans game, Magnus studies it: his mistakes go into his mistake library
and he rewrites his notebook. While the experiment runs, "game" and "yardstick"
are switched off, so no extra games mix into its results.

Options:  --model sonnet|opus|...  --effort low|medium|high|xhigh|max  --limit N (0 = none, the default)
"""

import argparse
import atexit
import json
import os
import re
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

import chess

import arbiter
import diary
import experiment as exp
import puzzles
from claude_agent import CALL_LOG, AgentUnavailable, ClaudeAgent, check_no_paid_api
from live import LiveStatus, demo_players, viewing_seconds
from notebook import (MISTAKES, NOTEBOOK, MistakeLibrary, Notebook, add_refutations, lessons_message,
                      write_lessons)
from openings import OpeningBook, by_name
from players import Turn
from stockfish import StockfishPlayer, open_engine

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


def make_agent(who: str, args, notebook_path=NOTEBOOK, mistakes_path=MISTAKES) -> ClaudeAgent:
    """Magnus (the learner) reads his notebook and similar past mistakes before every
    move; Hans (the control) has neither, and his move protocol has no notebook step."""
    if who == "magnus":
        agent = ClaudeAgent("Magnus", model=args.model, effort=args.effort, notebook_path=notebook_path,
                            mistakes=MistakeLibrary(mistakes_path), learner=True)
    else:
        agent = ClaudeAgent("Hans", model=args.model, effort=args.effort, learner=False)
    agent.expected_model = getattr(args, "model_id", None)
    return agent


def grade(d: dict) -> None:
    """Grades every move with full-strength Stockfish (free, about 15 seconds) and saves."""
    from review import review_diary
    from stockfish import open_engine
    engine = open_engine()
    try:
        summary = review_diary(d, engine)
    finally:
        engine.quit()
    diary.save_diary(d)
    for color in ("white", "black"):
        r = summary[color]
        print(f"Accuracy {d[color]['name']}: {r['accuracy']}% "
              f"({r['inaccuracies']} inaccuracies, {r['mistakes']} mistakes, {r['blunders']} blunders)")


def run_game(white, black, game_id: str, title: str, kind: str, notes: str,
             args, resume: bool, how_to_continue: str) -> dict | None:
    """Plays (or continues) one game, then grades it. None if Claude stopped answering.
    While it runs, the live view (docs/live.html) can follow it."""
    totals = {"requests": 0, "input_tokens": 0, "output_tokens": 0}
    started = time.time()
    live = LiveStatus(game_id, white.name, black.name)

    def show(m: dict) -> None:
        live.moved(m)
        if args.pause and m["thought_source"] not in ("move_description", "book"):
            time.sleep(viewing_seconds(m["thought"]))   # time to read it on the live page
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
        d = arbiter.play_game(white, black, game_id, title, kind=kind, move_limit=args.limit,
                              resume=resume, on_move=show, on_turn=live.turn, notes=notes)
    except AgentUnavailable as err:
        diary.rebuild_index()
        live.stopped(str(err))
        print(f"\nThe game stopped: {err}")
        print(f"Everything so far is saved. To continue later, run:\n   {how_to_continue}")
        return None
    minutes = (time.time() - started) / 60
    print(f"\nResult: {d['result_text']} after {(len(d['moves']) + 1) // 2} moves")
    print(f"Claude requests: {totals['requests']}, text in: {totals['input_tokens']} tokens, "
          f"text out: {totals['output_tokens']} tokens, time: {minutes:.0f} minutes")
    print(f"Saved: docs/games/{game_id}.json")
    live.finished(d)
    grade(d)
    live.write(graded=True)
    return d


def demo_live(args) -> int:
    """A free practice game for the live view: random moves with pauses and made-up thoughts."""
    white, black = demo_players()
    args.limit = args.limit or 20
    print("Demo game for the live view: random moves, made-up thoughts, no Claude requests.")
    print("Open http://localhost:8765/live.html (start serve.bat first) to watch.\n")
    d = run_game(white, black, f"{datetime.now():%Y-%m-%d-%H%M}-demo-live", "Demo: Magnus vs Hans (random moves)",
                 "test", "Demo game for testing the live view: random moves and made-up thoughts, no AI.",
                 args, False, "python arena/play.py demo-live")
    return 0 if d else 1


def play(args) -> int:
    """A Claude vs Claude test game, or a yardstick game against Stockfish."""
    if exp.load():
        print("Stopped: the experiment is running, and an extra game would appear among its games.")
        print("Use:   python arena/play.py experiment")
        return 1
    engine_player = None
    if args.what == "yardstick":
        engine_player = StockfishPlayer(skill=args.skill)
        agent = make_agent(args.agent, args)
        white, black = (agent, engine_player) if args.agent_color == "white" else (engine_player, agent)
        kind, label = "yardstick", f"{args.agent}-vs-stockfish"
        notes = f"Yardstick game: {agent.name} vs Stockfish at skill {args.skill}. No lessons are written."
    else:
        white = ClaudeAgent(args.white_name, model=args.model, effort=args.effort)
        black = ClaudeAgent(args.black_name, model=args.model, effort=args.effort)
        kind, label = "ai", "claude-vs-claude"
        notes = "Claude vs Claude test game. Both agents have no notebook."
    game_id = args.resume or f"{datetime.now():%Y-%m-%d-%H%M}-{label}"
    title = f"{white.name} vs {black.name} ({args.model}, {datetime.now():%d %b %Y})"
    try:
        d = run_game(white, black, game_id, title, kind, notes, args, bool(args.resume),
                     f"python arena/play.py {args.what} --resume {game_id}")
    finally:
        if engine_player:
            engine_player.close()
    return 0 if d else 1


# ---------- The experiment: Magnus vs Hans plus Stockfish checkpoints ----------

def experiment_games(games_dir: Path = diary.GAMES_DIR) -> list[dict]:
    """All games played so far (the experiment's are found by their ids)."""
    return [json.loads(p.read_text(encoding="utf-8")) for p in sorted(games_dir.glob("*.json"))
            if p.name != "index.json"]


def game_number(d: dict) -> int:
    return int(re.search(r"match-(\d+)", d["id"]).group(1))


def magnus_color(d: dict) -> str:
    return "white" if d["white"]["name"] == "Magnus" else "black"


def needs_lessons(d: dict) -> bool:
    """A finished Magnus vs Hans game that Magnus has not studied yet (wins included)."""
    return d.get("kind") == "match" and d["result"] != "*" and "lessons" not in d


def lessons_step(d: dict, args) -> bool:
    """Magnus studies the game: his mistakes go into the mistake library (free), and
    he rewrites his notebook (1 Claude request)."""
    color = magnus_color(d)
    engine = open_engine()
    try:
        if "review" not in d:
            from review import review_diary
            review_diary(d, engine)
        add_refutations(d, color, engine)   # how each mistake was punished
    finally:
        engine.quit()
    diary.save_diary(d)
    added = MistakeLibrary().add_game(d, color)
    print(f"\nMagnus studies game {game_number(d)}: {added} mistakes added to his mistake library.")
    try:
        record = write_lessons(d, color, make_agent("magnus", args))
    except AgentUnavailable as err:
        print(f"Stopped: {err}\nTo continue later, run:   python arena/play.py experiment")
        return False
    record["library_added"] = added
    d["lessons"] = record
    diary.save_diary(d)
    for lesson in record["new_lessons"]:
        print(f"   New or changed rule: {lesson}")
    if record["dropped"]:
        print(f"   {record['dropped']} earlier rules were merged, rewritten or replaced.")
    if record.get("problem"):
        print(f"   Note: {record['problem']}")
    print(f"   His notebook now has {record['notebook_size']} rules.")
    return True


def play_step(step: dict, resume_id: str | None, args) -> dict | None:
    """Plays (or continues) one game of the experiment."""
    game_id = resume_id or f"{datetime.now():%Y-%m-%d-%H%M}-{step['key']}"
    opening = by_name(step["opening"])
    engine_player = None
    if step["kind"] == "match":
        magnus, hans = make_agent("magnus", args), make_agent("hans", args)
        white, black = (magnus, hans) if step["magnus_white"] else (hans, magnus)
        title = f"Game {step['number']}: {white.name} vs {black.name}"
        notes = (f"Game {step['number']} of {exp.MATCH_GAMES} in the experiment, from the {opening['name']}. "
                 "Magnus (the learner) reads his notebook and similar past mistakes before every move; "
                 "Hans (the control) has neither.")
    else:
        agent = make_agent(step["agent"], args)
        engine_player = StockfishPlayer(skill=exp.YARDSTICK_SKILL, think_seconds=exp.YARDSTICK_THINK_SECONDS)
        white, black = (agent, engine_player) if step["color"] == "white" else (engine_player, agent)
        title = f"Checkpoint {step['checkpoint']}: {white.name} vs {black.name}"
        notes = (f"Checkpoint after game {step['checkpoint']}, from the {opening['name']}: {agent.name} plays "
                 f"the yardstick, Stockfish at skill {exp.YARDSTICK_SKILL}. Nothing is studied afterwards.")
    kind = "match" if step["kind"] == "match" else "yardstick"
    lessons_read = len(Notebook().lessons())   # the notebook does not change during a game
    try:
        d = run_game(OpeningBook(white, opening), OpeningBook(black, opening), game_id, title, kind, notes,
                     args, bool(resume_id), "python arena/play.py experiment")
    finally:
        if engine_player:
            engine_player.close()
    if d:
        d["opening"] = opening["name"]
        d["notebook_lessons"] = lessons_read
        diary.save_diary(d)
    return d


def puzzle_step(step: dict, args) -> bool:
    """The puzzle test for one player (about 30 Claude requests). Continues where it stopped."""
    agent = make_agent(step["agent"], args)
    print(f"{len(puzzles.load_set())} puzzles; answers are saved after each one.")
    engine = open_engine()
    try:
        finished = puzzles.run(step, agent, engine, pause=args.pause)
    finally:
        engine.quit()
    if finished and (s := puzzles.summary(step)):
        print(f"{s['agent']}: puzzle score {s['score']}%, Stockfish's best move found {s['best_found']} "
              f"times, {s['blunders']} blunders, {s['mistakes']} mistakes.")
    return finished


def pin_model(settings: dict) -> None:
    """After the first request, remembers which exact model the shortcut (e.g. "opus")
    stood for. From then on every answer must come from that model."""
    if settings.get("model_id") or not CALL_LOG.exists():
        return
    for line in reversed(CALL_LOG.read_text(encoding="utf-8").splitlines()):
        model = exp.main_model(json.loads(line).get("model") or [], settings["model"])
        if model:
            settings["model_id"] = model
            exp.save_settings(settings)
            print(f"The experiment's model is now pinned: {model}")
            return


def keep_awake() -> None:
    """Asks Windows not to fall asleep while this program runs (locking the screen is fine).
    Ends by itself when the program ends. Closing the lid can still send the laptop to sleep."""
    if sys.platform == "win32":
        import ctypes
        ES_CONTINUOUS, ES_SYSTEM_REQUIRED = 0x80000000, 0x00000001
        ctypes.windll.kernel32.SetThreadExecutionState(ES_CONTINUOUS | ES_SYSTEM_REQUIRED)


LOCK_FILE = diary.ROOT / "logs" / "experiment.lock"   # the process id of the runner playing right now


def process_running(pid: int) -> bool:
    if sys.platform == "win32":
        import ctypes
        handle = ctypes.windll.kernel32.OpenProcess(0x1000, False, pid)   # "query limited information"
        if not handle:
            return False
        code = ctypes.c_ulong()
        ctypes.windll.kernel32.GetExitCodeProcess(handle, ctypes.byref(code))
        ctypes.windll.kernel32.CloseHandle(handle)
        return code.value == 259   # STILL_ACTIVE
    try:
        os.kill(pid, 0)
        return True
    except OSError:
        return False


def take_lock() -> bool:
    """Only one runner at a time: two would play the same game and overwrite each other's moves."""
    if LOCK_FILE.exists():
        try:
            pid = int(LOCK_FILE.read_text().strip())
        except ValueError:
            pid = 0
        if pid and pid != os.getpid() and process_running(pid):
            print(f"Stopped: the experiment is already being played by another runner (process {pid}).")
            print("Only one may run at a time. Wait for it to finish, or stop it first.")
            return False
    LOCK_FILE.parent.mkdir(parents=True, exist_ok=True)
    LOCK_FILE.write_text(str(os.getpid()))
    atexit.register(lambda: LOCK_FILE.unlink(missing_ok=True))
    return True


def run_experiment(args) -> int:
    """Plays the experiment's next --games games, in order, continuing a stopped one first."""
    if not take_lock():
        return 1
    keep_awake()
    settings = exp.load()
    if not settings:
        print("The experiment has not been set up yet. Run first:   python arena/reset_experiment.py")
        return 1
    changes = exp.changes_since_lock(settings)
    if changes:
        print("Stopped: the settings changed since the experiment was locked, so new games")
        print("would not be comparable with earlier ones:")
        for change in changes:
            print(f"   {change}")
        print("Undo the change (git can show it), or start again with reset_experiment.py.")
        return 1
    args.model, args.effort = settings["model"], settings["effort"]
    args.model_id = settings.get("model_id")
    played = 0
    while True:
        games = experiment_games()
        for d in games:
            if needs_lessons(d):
                if not lessons_step(d, args):
                    return 1
                games = experiment_games()
        exp.save_results(games, settings)
        step, unfinished = exp.next_step(games)
        if step is None:
            print("\nThe experiment is complete! Every result is in docs/data/results.json.")
            return 0
        if played == args.games:
            print(f"\nNext time: {exp.step_title(step)}.   Run:   python arena/play.py experiment")
            return 0
        print(f"\n=== Experiment: {exp.step_title(step)}"
              f"{' (continuing where it stopped)' if unfinished else ''} ===")
        if step["kind"] == "puzzles":
            ok = puzzle_step(step, args)
        else:
            ok = play_step(step, unfinished["id"] if unfinished else None, args)
        pin_model(settings)
        args.model_id = settings.get("model_id")
        if not ok:
            return 1
        played += 1


# ---------- Dry run: see the messages without asking Claude ----------

SAMPLE_LESSONS = [
    "[opening] SAMPLE RULE (the real notebook is still empty): before taking a centre pawn with a knight, check "
    "whether the queen can then attack two of my pieces at once. Example: Nxe5 allowed Qg5.",
    "[middlegame] SAMPLE RULE: before capturing a pawn with my queen, count every enemy piece defending that pawn. "
    "Example: Qxd6 lost the queen to Bxd6.",
]
SAMPLE_MISTAKE = {   # the Blackburne trap: 4. Nxe5? Qg5!
    "game": "sample", "game_title": "SAMPLE GAME (the real library is still empty)", "ply": 7, "move": "4. Nxe5",
    "color": "white", "fen": "r1bqkbnr/pppp1ppp/8/4p3/2BnP3/5N2/PPPP1PPP/RNBQK2R w KQkq - 4 4",
    "san": "Nxe5", "thought": "I win a free pawn in the centre.", "best": "Nxd4",
    "refutation": "4... Qg5 5. Nxf7 Qxg2 6. Rf1 Qxe4+ 7. Be2 Nf3#", "win_before": 55.0, "win_after": 20.0,
    "label": "blunder", "phase": "opening", "material": [8, 2, 2, 2, 1, 8, 2, 2, 2, 1]}


def dry_run(args) -> int:
    notebook, library = Notebook(), MistakeLibrary()
    with tempfile.TemporaryDirectory() as tmp:
        if not notebook.lessons():
            notebook = Notebook(Path(tmp))
            notebook.save(SAMPLE_LESSONS, "sample")
        if not library.entries():
            library = MistakeLibrary(Path(tmp) / "mistakes.jsonl")
            library.path.write_text(json.dumps(SAMPLE_MISTAKE) + "\n", encoding="utf-8")
        magnus = make_agent("magnus", args, notebook_path=notebook.path, mistakes_path=library.path)
        hans = make_agent("hans", args)
        board = chess.Board()
        line = "=" * 70
        print(f"{line}\nWHAT MAGNUS IS SENT FOR HIS FIRST MOVE (as White)\n{line}")
        print(magnus.turn_message(Turn(board, "white")))
        print(f"{line}\nWHAT HANS IS SENT FOR THE SAME MOVE (no notebook, no mistake library)\n{line}")
        print(hans.turn_message(Turn(board, "white")))

        # The lesson-writing message, for the latest graded game with a Claude player.
        graded = [json.loads(p.read_text(encoding="utf-8")) for p in sorted(diary.GAMES_DIR.glob("*.json"))
                  if p.name != "index.json"]
        graded = [d for d in graded if "review" in d and "claude" in (d["white"]["type"], d["black"]["type"])]
        if graded:
            d = graded[-1]
            color = magnus_color(d) if d.get("kind") == "match" else (
                "white" if d["white"]["type"] == "claude" else "black")
            print(f"{line}\nWHAT MAGNUS WOULD BE SENT TO WRITE LESSONS AFTER: {d['title']}\n"
                  f"(he plays {color} in that game)\n{line}")
            print(lessons_message(d, color, notebook))
    print("No Claude requests were made.")
    return 0


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    check_no_paid_api()
    parser = argparse.ArgumentParser(description="Play chess with the Claude agents.")
    parser.add_argument("what", choices=["test-moves", "game", "yardstick", "experiment", "dry-run", "demo-live"])
    parser.add_argument("--model", default="sonnet")
    parser.add_argument("--effort", default="low", choices=["low", "medium", "high", "xhigh", "max"])
    parser.add_argument("--limit", type=int, default=0,
                        help="moves per side before a draw is declared (0 = no limit)")
    parser.add_argument("--resume", help="game/yardstick: id of an unfinished game to continue")
    parser.add_argument("--white-name", default="Claude A")
    parser.add_argument("--black-name", default="Claude B")
    parser.add_argument("--agent", default="magnus", choices=["magnus", "hans"],
                        help="yardstick: who plays Stockfish")
    parser.add_argument("--agent-color", default="white", choices=["white", "black"],
                        help="yardstick: which colour the agent plays")
    parser.add_argument("--skill", type=int, default=0, help="yardstick: Stockfish skill level (0-20)")
    parser.add_argument("--games", type=int, default=1,
                        help="experiment: how many steps to play (a game, or one player's puzzle test)")
    parser.add_argument("--no-pause", dest="pause", action="store_false",
                        help="do not wait after each move for the live page (faster, for unattended runs)")
    args = parser.parse_args()
    actions = {"test-moves": test_moves, "experiment": run_experiment, "dry-run": dry_run, "demo-live": demo_live}
    return actions.get(args.what, play)(args)


if __name__ == "__main__":
    sys.exit(main())
