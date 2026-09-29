"""
Builds "diary" files: one JSON file per game, holding every move plus what
the player was thinking. The replay website reads these files.

The arbiter works out every chess detail here (which piece moved, captures,
castling, en passant, promotion, check), so the website never needs to know
the rules of chess. It only has to animate what the diary says.

This file is shared by the sample-game converter and, later, the arbiter.
"""

import json
from datetime import date
from pathlib import Path

import chess

DIARY_FORMAT_VERSION = 1

# The website folder where diaries are saved (docs/games).
GAMES_DIR = Path(__file__).resolve().parent.parent / "docs" / "games"

PIECE_NAMES = {
    chess.PAWN: "Pawn",
    chess.KNIGHT: "Knight",
    chess.BISHOP: "Bishop",
    chess.ROOK: "Rook",
    chess.QUEEN: "Queen",
    chess.KING: "King",
}


def describe_move(board: chess.Board, move: chess.Move) -> str:
    """A plain-English description of a move, e.g. 'Knight takes Pawn on e5.'
    `board` is the position BEFORE the move is played."""
    if board.is_kingside_castling(move):
        text = "Castles kingside."
    elif board.is_queenside_castling(move):
        text = "Castles queenside."
    else:
        piece = PIECE_NAMES[board.piece_type_at(move.from_square)]
        to_name = chess.square_name(move.to_square)
        if board.is_en_passant(move):
            text = f"{piece} takes Pawn en passant, landing on {to_name}."
        elif board.is_capture(move):
            captured = PIECE_NAMES[board.piece_type_at(move.to_square)]
            text = f"{piece} takes {captured} on {to_name}."
        else:
            text = f"{piece} to {to_name}."
        if move.promotion:
            text = text[:-1] + f" and becomes a {PIECE_NAMES[move.promotion]}."

    after = board.copy(stack=False)
    after.push(move)
    if after.is_checkmate():
        text += " Checkmate!"
    elif after.is_check():
        text += " Check!"
    return text


def move_record(board: chess.Board, move: chess.Move, thought: str,
                thought_source: str, illegal_attempts: int = 0) -> dict:
    """Everything the website needs to show one move.
    `board` is the position BEFORE the move; it is not changed."""
    color = "white" if board.turn == chess.WHITE else "black"
    piece = board.piece_at(move.from_square)
    record = {
        "ply": board.ply() + 1,               # half-move count: 1, 2, 3...
        "move_number": board.fullmove_number,  # the number shown in chess notation
        "color": color,
        "san": board.san(move),                # normal chess notation, e.g. Nxe5
        "uci": move.uci(),                     # computer notation, e.g. g1f3
        "from": chess.square_name(move.from_square),
        "to": chess.square_name(move.to_square),
        "piece": piece.symbol().upper(),       # P N B R Q K
        "captured": None,
        "capture_square": None,
        "castling": None,
        "rook_from": None,
        "rook_to": None,
        "en_passant": board.is_en_passant(move),
        "promotion": chess.piece_symbol(move.promotion).upper() if move.promotion else None,
        "check": False,
        "checkmate": False,
        "fen_after": None,
        "thought": thought,
        "thought_source": thought_source,
        "illegal_attempts": illegal_attempts,
    }

    if board.is_en_passant(move):
        # The captured pawn is NOT on the square the capturing pawn lands on.
        captured_sq = chess.square(chess.square_file(move.to_square),
                                   chess.square_rank(move.from_square))
        record["captured"] = "P"
        record["capture_square"] = chess.square_name(captured_sq)
    elif board.is_capture(move):
        record["captured"] = board.piece_at(move.to_square).symbol().upper()
        record["capture_square"] = chess.square_name(move.to_square)

    if board.is_castling(move):
        rank = "1" if color == "white" else "8"
        if board.is_kingside_castling(move):
            record.update(castling="kingside", rook_from="h" + rank, rook_to="f" + rank)
        else:
            record.update(castling="queenside", rook_from="a" + rank, rook_to="d" + rank)

    after = board.copy(stack=False)
    after.push(move)
    record["check"] = after.is_check()
    record["checkmate"] = after.is_checkmate()
    record["fen_after"] = after.fen()
    return record


def result_text(result: str, termination: str) -> str:
    """A friendly sentence like 'White wins by checkmate'."""
    winner = {"1-0": "White", "0-1": "Black"}.get(result)
    loser = {"1-0": "Black", "0-1": "White"}.get(result)
    if termination == "checkmate":
        return f"{winner} wins by checkmate"
    if termination == "resignation":
        return f"{winner} wins ({loser} resigned)"
    if result == "1/2-1/2":
        return {
            "stalemate": "Draw by stalemate",
            "repetition": "Draw by repetition",
            "fifty_moves": "Draw by the 50-move rule",
            "insufficient_material": "Draw: not enough pieces left to checkmate",
            "move_limit": "Draw: move limit reached",
        }.get(termination, "Draw agreed")
    if result == "*":
        return "Game not finished"
    return f"{winner} wins"


def new_diary(game_id: str, title: str, kind: str, white: dict, black: dict,
              event: str = "", game_date: str = "", notes: str = "",
              start_fen: str = chess.STARTING_FEN) -> dict:
    """An empty diary, ready for moves to be added."""
    return {
        "format_version": DIARY_FORMAT_VERSION,
        "id": game_id,
        "title": title,
        "kind": kind,              # "sample", "test" or (later) "ai"
        "event": event,
        "date": game_date or date.today().isoformat(),
        "white": white,            # e.g. {"name": "Garry Kasparov", "type": "human"}
        "black": black,
        "notes": notes,
        "start_fen": start_fen,
        "result": "*",
        "winner": None,
        "termination": None,
        "result_text": "Game not finished",
        "moves": [],
    }


def finish_diary(diary: dict, result: str, termination: str) -> None:
    diary["result"] = result
    diary["winner"] = {"1-0": "white", "0-1": "black"}.get(result)
    diary["termination"] = termination
    diary["result_text"] = result_text(result, termination)


def save_diary(diary: dict, games_dir: Path = GAMES_DIR, update_index: bool = True) -> Path:
    """Saves a diary as <games_dir>/<id>.json. The arbiter saves after every
    move (update_index=False) and updates the game list once at the end."""
    games_dir.mkdir(parents=True, exist_ok=True)
    path = games_dir / f"{diary['id']}.json"
    path.write_text(json.dumps(diary, indent=2, ensure_ascii=False), encoding="utf-8")
    if update_index:
        rebuild_index(games_dir)
    return path


def rebuild_index(games_dir: Path = GAMES_DIR) -> Path:
    """Writes index.json: the list of games the website offers."""
    games = []
    for path in sorted(games_dir.glob("*.json")):
        if path.name == "index.json":
            continue
        d = json.loads(path.read_text(encoding="utf-8"))
        games.append({
            "id": d["id"],
            "file": path.name,
            "title": d["title"],
            "kind": d["kind"],
            "date": d["date"],
            "white": d["white"]["name"],
            "black": d["black"]["name"],
            "result_text": d["result_text"],
            "moves": len(d["moves"]),
        })
    index_path = games_dir / "index.json"
    index_path.write_text(json.dumps({"games": games}, indent=2, ensure_ascii=False),
                          encoding="utf-8")
    return index_path
