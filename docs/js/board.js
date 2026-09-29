/*
 * Draws the chess board and pieces on the page.
 *
 * The board reads a position written in FEN (a standard one-line text
 * description of where every piece stands) and places the piece pictures.
 * It knows nothing about chess rules: the Python arbiter has already
 * checked everything and written it into the diary.
 */

const FILES = "abcdefgh";

class ChessBoard {
  constructor(frameElement) {
    this.frame = frameElement;
    this.board = frameElement.querySelector(".board");
    this.flipped = false;
    this.pieces = {}; // square name (e.g. "e4") -> <img> element
    this.drawCoordinates();
    // Coloured squares under the pieces: last move (yellow) and check (red).
    this.highlights = document.createElement("div");
    this.highlights.className = "highlights";
    this.board.appendChild(this.highlights);
    this.lastMove = null;
    this.checkSquare = null;
    this.onFlip = null;  // other parts (e.g. the speech bubble) can react to a flip
  }

  /* Reads the piece placement part of a FEN into { "e1": "wK", ... }. */
  static parseFen(fen) {
    const placement = fen.split(" ")[0];
    const result = {};
    placement.split("/").forEach((row, i) => {
      const rank = 8 - i;
      let file = 0;
      for (const ch of row) {
        if (/\d/.test(ch)) {
          file += Number(ch);
        } else {
          const color = ch === ch.toUpperCase() ? "w" : "b";
          result[FILES[file] + rank] = color + ch.toUpperCase();
          file += 1;
        }
      }
    });
    return result;
  }

  /* Which column and row (0-7, from the top-left) a square is shown in. */
  squareCell(square) {
    let col = FILES.indexOf(square[0]);
    let row = 8 - Number(square[1]);
    if (this.flipped) { col = 7 - col; row = 7 - row; }
    return { col, row };
  }

  /* Where a square sits on screen, as percentages from the top-left corner. */
  squarePosition(square) {
    const { col, row } = this.squareCell(square);
    return { left: col * 12.5 + "%", top: row * 12.5 + "%" };
  }

  /* Shows the last move's two squares and a king in check.
     lastMove is { from, to } or null; checkSquare is a square or null. */
  setHighlights(lastMove, checkSquare) {
    this.lastMove = lastMove;
    this.checkSquare = checkSquare;
    this.drawHighlights();
  }

  drawHighlights() {
    this.highlights.replaceChildren();
    const add = (square, cls) => {
      const div = document.createElement("div");
      div.className = cls;
      Object.assign(div.style, this.squarePosition(square));
      this.highlights.appendChild(div);
    };
    if (this.lastMove) {
      add(this.lastMove.from, "hl-last");
      add(this.lastMove.to, "hl-last");
    }
    if (this.checkSquare) add(this.checkSquare, "hl-check");
  }

  /* The square of a king ("w" or "b") in the position shown. */
  findKing(color) {
    for (const [square, img] of Object.entries(this.pieces)) {
      if (img.dataset.code === color + "K") return square;
    }
    return null;
  }

  /* Removes all pieces and draws a position from a FEN. */
  setPosition(fen) {
    this.board.querySelectorAll(".piece").forEach((img) => img.remove());
    this.pieces = {};
    for (const [square, code] of Object.entries(ChessBoard.parseFen(fen))) {
      const img = document.createElement("img");
      img.className = "piece";
      img.src = `pieces/${code}.svg`;
      img.alt = code;
      img.dataset.code = code;
      Object.assign(img.style, this.squarePosition(square));
      this.board.appendChild(img);
      this.pieces[square] = img;
    }
  }

  /* Plays one move from the diary on the board.
     `m` is a move record (from, to, captured, castling, promotion ...).
     With animate=false the pieces jump instead of sliding. */
  applyMove(m, animate = true) {
    this.board.classList.toggle("no-animation", !animate);

    // 1. Remove a captured piece. For en passant it is on a different square.
    if (m.capture_square) {
      const victim = this.pieces[m.capture_square];
      delete this.pieces[m.capture_square];
      if (victim) this.removePiece(victim, animate);
    }

    // 2. Move the piece itself.
    this.slide(m.from, m.to);

    // 3. Castling also moves the rook.
    if (m.castling) this.slide(m.rook_from, m.rook_to);

    // 4. Promotion: the pawn turns into the new piece.
    if (m.promotion) {
      const img = this.pieces[m.to];
      const code = img.dataset.code[0] + m.promotion;
      img.dataset.code = code;
      img.alt = code;
      const swap = () => { img.src = `pieces/${code}.svg`; };
      animate ? setTimeout(swap, 250) : swap();
    }
  }

  slide(from, to) {
    const img = this.pieces[from];
    if (!img) throw new Error(`No piece on ${from}`);
    delete this.pieces[from];
    this.pieces[to] = img;
    img.classList.add("moving");
    Object.assign(img.style, this.squarePosition(to));
    setTimeout(() => img.classList.remove("moving"), 300);
  }

  removePiece(img, animate) {
    if (!animate) { img.remove(); return; }
    img.classList.add("captured");
    setTimeout(() => img.remove(), 250);
  }

  /* The position currently shown, as { "e1": "wK", ... }. */
  currentPlacement() {
    const result = {};
    for (const [square, img] of Object.entries(this.pieces)) result[square] = img.dataset.code;
    return result;
  }

  /* True if the pieces on screen are exactly the pieces in `fen`. */
  matchesFen(fen) {
    const shown = this.currentPlacement();
    const expected = ChessBoard.parseFen(fen);
    const squares = new Set([...Object.keys(shown), ...Object.keys(expected)]);
    for (const sq of squares) if (shown[sq] !== expected[sq]) return false;
    return true;
  }

  /* Turns the board around so Black is at the bottom (or back again). */
  flip() {
    this.flipped = !this.flipped;
    for (const [square, img] of Object.entries(this.pieces)) {
      Object.assign(img.style, this.squarePosition(square));
    }
    this.drawCoordinates();
    this.drawHighlights();
    if (this.onFlip) this.onFlip();
  }

  /* Writes the letters a-h in the bottom row and numbers 1-8 in the left
     column, inside the squares. */
  drawCoordinates() {
    this.board.querySelectorAll(".coords").forEach((el) => el.remove());
    const layer = document.createElement("div");
    layer.className = "coords";
    for (let i = 0; i < 8; i++) {
      // Letter in the bottom row, column i (counting from the left).
      const file = this.flipped ? FILES[7 - i] : FILES[i];
      const bottomRank = this.flipped ? 8 : 1;
      layer.appendChild(this.coordLabel(file, file + bottomRank,
        { left: `calc(${(i + 1) * 12.5}% - 0.6em)`, bottom: "0.35em" }));
      // Number in the left column, row i (counting from the top).
      const rank = this.flipped ? i + 1 : 8 - i;
      const leftFile = this.flipped ? "h" : "a";
      layer.appendChild(this.coordLabel(rank, leftFile + rank,
        { left: "0.3em", top: `calc(${i * 12.5}% + 0.3em)` }));
    }
    this.board.appendChild(layer);
  }

  coordLabel(text, square, style) {
    const span = document.createElement("span");
    span.textContent = text;
    span.className = ChessBoard.isLightSquare(square) ? "on-light" : "on-dark";
    Object.assign(span.style, style);
    return span;
  }

  /* a1 is dark; squares alternate from there. */
  static isLightSquare(square) {
    return (FILES.indexOf(square[0]) + Number(square[1])) % 2 === 0;
  }
}
