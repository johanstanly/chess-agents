"""
The arbiter: ordinary code (no AI) that runs a game between two players.

- Asks the player whose turn it is for a move (a text suggestion).
- Checks the suggestion with python-chess. If it cannot be read or is not
  legal, the arbiter explains why and asks again, up to MAX_ATTEMPTS times.
  If every try fails, it plays a random legal move and marks it clearly.
- Ends the game by the rules: checkmate, stalemate, not enough pieces,
  threefold repetition, the 50-move rule, or the move limit.
- Saves the diary after every move, so nothing is lost if a game stops.
"""

import json
import random
import re
from pathlib import Path

import chess

import diary
from players import Player, Turn

MAX_ATTEMPTS = 3        # tries a player gets for each move
MOVE_LIMIT = 60         # moves per side before the game is declared a draw


def read_move(board: chess.Board, text: str) -> tuple[chess.Move | None, str]:
    """Turns a suggestion like "Nf3", "O-O", "e8=Q" or "g1f3" into a legal move.
    Returns (move, "") if legal, or (None, reason) if not."""
    cleaned = text.strip().strip(".").replace("0-0-0", "O-O-O").replace("0-0", "O-O")
    cleaned = re.sub(r"[!?]+$", "", cleaned).strip()
    if not cleaned:
        return None, "No move was given."
    if " " in cleaned:
        return None, f"'{text}' is not a single move."

    # Computer notation: from-square + to-square (+ promotion piece), e.g. g1f3, e7e8q.
    if re.fullmatch(r"[a-h][1-8][a-h][1-8][qrbnQRBN]?", cleaned):
        move = chess.Move.from_uci(cleaned.lower())
        if move in board.legal_moves:
            return move, ""
        # A pawn reaching the last rank without saying which piece: assume a queen.
        queen = chess.Move(move.from_square, move.to_square, promotion=chess.QUEEN)
        if queen in board.legal_moves:
            return queen, ""
        return None, f"'{cleaned}' is not legal in this position."

    # Normal chess notation, e.g. Nf3, exd5, O-O, e8=Q.
    try:
        return board.parse_san(cleaned), ""
    except chess.IllegalMoveError:
        return None, f"'{cleaned}' is not legal in this position."
    except chess.AmbiguousMoveError:
        return None, f"'{cleaned}' is ambiguous: more than one piece can make that move. Say which one, e.g. Nbd2."
    except ValueError:
        return None, f"Could not read '{text}' as a chess move."


def game_over(board: chess.Board, move_limit: int) -> tuple[str, str] | None:
    """(result, termination) if the game has ended, otherwise None."""
    if board.is_checkmate():
        return ("0-1" if board.turn == chess.WHITE else "1-0"), "checkmate"
    if board.is_stalemate():
        return "1/2-1/2", "stalemate"
    if board.is_insufficient_material():
        return "1/2-1/2", "insufficient_material"
    if board.is_repetition(3):
        return "1/2-1/2", "repetition"
    if board.halfmove_clock >= 100:
        return "1/2-1/2", "fifty_moves"
    if move_limit and board.fullmove_number > move_limit:  # 0 = no limit
        return "1/2-1/2", "move_limit"
    return None


def play_game(white: Player, black: Player, game_id: str, title: str,
              kind: str = "test", games_dir: Path = diary.GAMES_DIR,
              start_fen: str = chess.STARTING_FEN, move_limit: int = MOVE_LIMIT,
              seed: int | None = None, notes: str = "", log=print,
              resume: bool = False, on_move=None) -> dict:
    """Plays one full game and returns its diary (also saved to games_dir).
    With resume=True, an unfinished game with the same id is continued from
    where it stopped (e.g. after the Pro plan usage limit resets)."""
    saved = games_dir / f"{game_id}.json"
    if resume and saved.exists():
        d = json.loads(saved.read_text(encoding="utf-8"))
        if d["result"] != "*":
            log(f"{game_id} is already finished: {d['result_text']}")
            return d
        board = chess.Board(d["start_fen"])
        for m in d["moves"]:
            board.push_uci(m["uci"])
        log(f"Continuing {game_id} from half-move {len(d['moves']) + 1}")
    else:
        board = chess.Board(start_fen)
        d = diary.new_diary(game_id, title, kind, white.info(), black.info(),
                            notes=notes, start_fen=start_fen)
    fallback_rng = random.Random(seed)
    for player in (white, black):
        if hasattr(player, "game_id"):
            player.game_id = game_id  # lets AI agents label their usage log

    while (ending := game_over(board, move_limit)) is None:
        color = "white" if board.turn == chess.WHITE else "black"
        player = white if board.turn == chess.WHITE else black
        feedback, illegal = [], []
        move, suggestion = None, None

        usage = {"requests": 0, "input_tokens": 0, "output_tokens": 0, "seconds": 0.0}
        for _ in range(MAX_ATTEMPTS):
            suggestion = player.suggest(Turn(board.copy(), color, list(feedback)))
            if getattr(player, "last_usage", None):
                usage["requests"] += 1
                for key in ("input_tokens", "output_tokens", "seconds"):
                    usage[key] += player.last_usage[key]
            move, problem = read_move(board, suggestion.move_text)
            if move:
                break
            # If no move could be found at all, keep the start of what was written.
            illegal.append(suggestion.move_text or f"(no move found in: {suggestion.raw[:150]!r})")
            feedback.append(problem)

        if move:
            record = diary.move_record(board, move, suggestion.thought,
                                       suggestion.thought_source, len(illegal))
        else:
            move = fallback_rng.choice(list(board.legal_moves))
            record = diary.move_record(
                board, move,
                f"The arbiter played a random move: {player.name} gave no legal move "
                f"in {MAX_ATTEMPTS} tries.",
                "arbiter_fallback", len(illegal))
            record["fallback"] = True
        if illegal:
            record["illegal_suggestions"] = illegal
        if usage["requests"]:
            usage["seconds"] = round(usage["seconds"], 1)
            record["usage"] = usage  # how much of the Pro allowance this move used

        d["moves"].append(record)
        board.push(move)
        diary.save_diary(d, games_dir, update_index=False)
        if on_move:
            on_move(record)  # e.g. print progress

    result, termination = ending
    diary.finish_diary(d, result, termination)
    diary.save_diary(d, games_dir)
    log(f"{game_id}: {d['result_text']} after {(len(d['moves']) + 1) // 2} moves")
    return d
