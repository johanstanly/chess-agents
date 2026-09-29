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
    if board.fullmove_number > move_limit:
        return "1/2-1/2", "move_limit"
    return None


def play_game(white: Player, black: Player, game_id: str, title: str,
              kind: str = "test", games_dir: Path = diary.GAMES_DIR,
              start_fen: str = chess.STARTING_FEN, move_limit: int = MOVE_LIMIT,
              seed: int | None = None, notes: str = "", log=print) -> dict:
    """Plays one full game and returns its diary (also saved to games_dir)."""
    board = chess.Board(start_fen)
    d = diary.new_diary(game_id, title, kind, white.info(), black.info(),
                        notes=notes, start_fen=start_fen)
    fallback_rng = random.Random(seed)

    while (ending := game_over(board, move_limit)) is None:
        color = "white" if board.turn == chess.WHITE else "black"
        player = white if board.turn == chess.WHITE else black
        feedback, illegal = [], []
        move, suggestion = None, None

        for _ in range(MAX_ATTEMPTS):
            suggestion = player.suggest(Turn(board.copy(), color, list(feedback)))
            move, problem = read_move(board, suggestion.move_text)
            if move:
                break
            illegal.append(suggestion.move_text)
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

        d["moves"].append(record)
        board.push(move)
        diary.save_diary(d, games_dir, update_index=False)

    result, termination = ending
    diary.finish_diary(d, result, termination)
    diary.save_diary(d, games_dir)
    log(f"{game_id}: {d['result_text']} after {(len(d['moves']) + 1) // 2} moves")
    return d
