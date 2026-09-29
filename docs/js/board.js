/*
 * Draws the chess board and pieces on the page.
 *
 * The board reads a position written in FEN (a standard one-line text
 * description of where every piece stands) and places the piece pictures.
 * It knows nothing about chess rules: the Python referee has already
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

  /* Where a square sits on screen, as percentages from the top-left corner. */
  squarePosition(square) {
    let col = FILES.indexOf(square[0]);
    let row = 8 - Number(square[1]);
    if (this.flipped) { col = 7 - col; row = 7 - row; }
    return { left: col * 12.5 + "%", top: row * 12.5 + "%" };
  }

  /* Removes all pieces and draws a position from a FEN. */
  setPosition(fen) {
    for (const img of Object.values(this.pieces)) img.remove();
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

  /* Turns the board around so Black is at the bottom (or back again). */
  flip() {
    this.flipped = !this.flipped;
    for (const [square, img] of Object.entries(this.pieces)) {
      Object.assign(img.style, this.squarePosition(square));
    }
    this.drawCoordinates();
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
