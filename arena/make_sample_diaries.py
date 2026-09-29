"""
Turns the real games in samples/ (PGN files) into diary files in docs/games/.

Every move is checked by python-chess. If a game contains an illegal move,
no diary is made for it.

Run:   python arena/make_sample_diaries.py            (all games in samples/)
  or:  python arena/make_sample_diaries.py some.pgn   (just the files you name)
"""

import logging
import sys
from pathlib import Path

import chess
import chess.pgn

import diary

SAMPLES_DIR = Path(__file__).resolve().parent.parent / "samples"

# python-chess also prints its own copy of PGN errors; we report them ourselves.
logging.getLogger("chess.pgn").setLevel(logging.CRITICAL)


def find_termination(board: chess.Board, result: str) -> str:
    """Why the game ended, judged from the final position and the result."""
    if board.is_checkmate():
        return "checkmate"
    if board.is_stalemate():
        return "stalemate"
    if board.is_insufficient_material():
        return "insufficient_material"
    if result in ("1-0", "0-1"):
        return "resignation"
    if result == "1/2-1/2":
        return "agreement"
    return "unfinished"


def convert(pgn_path: Path) -> bool:
    """Converts one PGN file. Returns True if a diary was saved."""
    with open(pgn_path, encoding="utf-8") as f:
        game = chess.pgn.read_game(f)

    if game is None:
        print(f"REFUSED  {pgn_path.name}: no chess game found in the file.")
        return False
    if game.errors:
        print(f"REFUSED  {pgn_path.name}: contains an illegal or unreadable move.")
        for err in game.errors:
            print(f"         -> {err}")
        return False

    h = game.headers
    result = h.get("Result", "*")
    d = diary.new_diary(
        game_id=h.get("Id", pgn_path.stem),
        title=h.get("Title", f"{h.get('White')} vs {h.get('Black')}"),
        kind=h.get("Kind", "sample"),
        white={"name": h.get("White", "White"), "type": "human"},
        black={"name": h.get("Black", "Black"), "type": "human"},
        event=f"{h.get('Event', '')}, {h.get('Site', '')}".strip(", "),
        game_date=h.get("Date", "").replace(".??", "").replace(".", "-"),
        notes=("Sample game for testing the replay. The 'thoughts' are short notes "
               "written by hand (or plain move descriptions), not real AI thinking."),
    )

    board = game.board()
    for node in game.mainline():
        move = node.move
        if node.comment.strip():
            thought, source = node.comment.strip(), "sample_note"
        else:
            thought, source = diary.describe_move(board, move), "move_description"
        d["moves"].append(diary.move_record(board, move, thought, source))
        board.push(move)

    termination = find_termination(board, result)
    # Safety check: a checkmate must match the stated winner.
    if termination == "checkmate":
        real = "1-0" if board.turn == chess.BLACK else "0-1"
        if result != real:
            print(f"REFUSED  {pgn_path.name}: says {result} but the final position is {real}.")
            return False
    diary.finish_diary(d, result, termination)
    path = diary.save_diary(d)

    moves = d["moves"]
    castled = {c: next((m["castling"] for m in moves if m["color"] == c and m["castling"]), None)
               for c in ("white", "black")}
    print(f"OK       {d['title']}")
    print(f"         {(len(moves) + 1) // 2} moves ({len(moves)} half-moves)"
          f" | {sum(1 for m in moves if m['captured'])} captures"
          f" | {sum(1 for m in moves if m['check'])} checks"
          f" | {sum(1 for m in moves if m['en_passant'])} en passant"
          f" | {sum(1 for m in moves if m['promotion'])} promotions")
    print(f"         White castled: {castled['white'] or 'no'}"
          f" | Black castled: {castled['black'] or 'no'}")
    print(f"         Ending: {d['result_text']}  [{result}]")
    print(f"         Thoughts: {sum(1 for m in moves if m['thought_source'] == 'sample_note')}"
          f" sample notes, the rest are move descriptions")
    print(f"         Saved: docs/games/{path.name}")
    return True


def main() -> int:
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8")
    paths = [Path(p) for p in sys.argv[1:]] or sorted(SAMPLES_DIR.glob("*.pgn"))
    ok = [convert(p) for p in paths]
    print(f"\n{sum(ok)} of {len(ok)} games converted.")
    return 0 if all(ok) else 1


if __name__ == "__main__":
    sys.exit(main())
