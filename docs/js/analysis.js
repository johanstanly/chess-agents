/*
 * Analysis mode: lets you drag or click pieces to try your own moves at any
 * point in a game. chess.js (a chess-rules library) checks your moves are
 * legal. The real game is never changed; "Back to game" returns to it.
 */

class Analysis {
  constructor(board, replay, Chess, onChange) {
    this.board = board;
    this.replay = replay;
    this.Chess = Chess;          // the chess.js rules library
    this.onChange = onChange;    // called whenever the position changes
    this.active = false;
    this.chess = null;           // rules for the analysis position
    this.line = [];              // your moves so far, in chess notation
    this.startFen = null;
    this.selected = null;        // square of the piece you picked up
    this.drag = null;
    this.marks = document.createElement("div");
    this.marks.className = "marks";
    board.board.appendChild(this.marks);
    this.listen();
  }

  /* The rules for the position on screen right now. */
  rules() {
    return this.active ? this.chess : new this.Chess(this.replay.expectedFen());
  }

  fen() {
    return this.active ? this.chess.fen() : this.replay.expectedFen();
  }

  enter() {
    this.active = true;
    this.startFen = this.replay.expectedFen();
    this.chess = new this.Chess(this.startFen);
    this.line = [];
    this.board.board.classList.add("analysis");
  }

  /* Leaves analysis and shows the real game again, at the same move. */
  exit() {
    if (!this.active) return;
    this.active = false;
    this.chess = null;
    this.line = [];
    this.clearSelection();
    this.board.board.classList.remove("analysis");
    this.board.setPosition(this.replay.expectedFen());
    this.replay.update();
  }

  /* Tries a move from one square to another. Returns true if it was legal. */
  tryMove(from, to) {
    const rules = this.rules();
    let move;
    try {
      move = rules.move({ from, to, promotion: "q" });  // pawns always become queens
    } catch {
      return false;  // illegal: chess.js refuses it
    }
    if (!this.active) {
      this.enter();
      this.chess.move({ from, to, promotion: "q" });
    }
    this.line.push(move.san);
    this.board.applyMove(Analysis.toRecord(move), true);
    this.onChange();
    return true;
  }

  /* Takes back your last analysis move; after the first one, back to the game. */
  back() {
    this.chess.undo();
    this.line.pop();
    if (this.line.length === 0) { this.exit(); return; }
    this.board.setPosition(this.chess.fen());
    this.onChange();
  }

  /* Your moves written like "24... Kb8 25. Qe5". */
  lineText() {
    const [, side, , , , moveNo] = this.startFen.split(" ");
    let n = Number(moveNo);
    let white = side === "w";
    const parts = [];
    this.line.forEach((san, i) => {
      if (white) parts.push(`${n}. ${san}`);
      else parts.push(i === 0 ? `${n}... ${san}` : san);
      if (!white) n += 1;
      white = !white;
    });
    return parts.join(" ");
  }

  /* Converts a chess.js move into the same kind of record the diary uses,
     so the board can animate it in exactly the same way. */
  static toRecord(m) {
    const rank = m.color === "w" ? "1" : "8";
    const record = {
      from: m.from, to: m.to,
      capture_square: null, castling: null, rook_from: null, rook_to: null,
      promotion: m.promotion ? m.promotion.toUpperCase() : null,
    };
    if (m.flags.includes("e")) record.capture_square = m.to[0] + m.from[1];
    else if (m.captured) record.capture_square = m.to;
    if (m.flags.includes("k")) Object.assign(record, { castling: "kingside", rook_from: "h" + rank, rook_to: "f" + rank });
    if (m.flags.includes("q")) Object.assign(record, { castling: "queenside", rook_from: "a" + rank, rook_to: "d" + rank });
    return record;
  }

  /* ---------- Mouse and touch ---------- */

  squareAt(clientX, clientY) {
    const r = this.board.board.getBoundingClientRect();
    let col = Math.floor(((clientX - r.left) / r.width) * 8);
    let row = Math.floor(((clientY - r.top) / r.height) * 8);
    if (col < 0 || col > 7 || row < 0 || row > 7) return null;
    if (this.board.flipped) { col = 7 - col; row = 7 - row; }
    return "abcdefgh"[col] + (8 - row);
  }

  listen() {
    const el = this.board.board;
    el.addEventListener("pointerdown", (e) => this.onDown(e));
    el.addEventListener("pointermove", (e) => this.onMove(e));
    el.addEventListener("pointerup", (e) => this.onUp(e));
    el.addEventListener("pointercancel", () => this.cancelDrag());
  }

  onDown(e) {
    const square = this.squareAt(e.clientX, e.clientY);
    if (!square) return;
    // Second click of click-click: move to the chosen square.
    if (this.selected && this.targets.includes(square)) {
      const from = this.selected;
      this.clearSelection();
      this.tryMove(from, square);
      return;
    }
    const rules = this.rules();
    const piece = rules.get(square);
    if (!piece || piece.color !== rules.turn()) { this.clearSelection(); return; }

    this.select(square, rules);
    const img = this.board.pieces[square];
    if (!img) return;
    e.preventDefault();
    this.board.board.setPointerCapture(e.pointerId);
    this.drag = { square, img, moved: false };
    img.classList.add("dragging");
    this.followPointer(e);
  }

  onMove(e) {
    if (!this.drag) return;
    this.drag.moved = true;
    this.followPointer(e);
  }

  onUp(e) {
    if (!this.drag) return;
    const { square, img } = this.drag;
    img.classList.remove("dragging");
    this.drag = null;
    const target = this.squareAt(e.clientX, e.clientY);
    if (target && target !== square && this.targets.includes(target)) {
      this.clearSelection();
      this.tryMove(square, target);
    } else {
      // Dropped back or on an illegal square: the piece goes home.
      Object.assign(img.style, this.board.squarePosition(square));
    }
  }

  cancelDrag() {
    if (!this.drag) return;
    this.drag.img.classList.remove("dragging");
    Object.assign(this.drag.img.style, this.board.squarePosition(this.drag.square));
    this.drag = null;
  }

  followPointer(e) {
    const r = this.board.board.getBoundingClientRect();
    const x = ((e.clientX - r.left) / r.width) * 100 - 6.25;
    const y = ((e.clientY - r.top) / r.height) * 100 - 6.25;
    this.drag.img.style.left = x + "%";
    this.drag.img.style.top = y + "%";
  }

  /* Highlights the picked-up piece and shows dots where it can go. */
  select(square, rules) {
    this.clearSelection();
    this.selected = square;
    this.targets = rules.moves({ square, verbose: true }).map((m) => m.to);
    this.mark(square, "mark-selected");
    for (const t of this.targets) this.mark(t, rules.get(t) ? "mark-capture" : "mark-dot");
  }

  mark(square, cls) {
    const div = document.createElement("div");
    div.className = cls;
    Object.assign(div.style, this.board.squarePosition(square));
    this.marks.appendChild(div);
  }

  clearSelection() {
    this.selected = null;
    this.targets = [];
    this.marks.replaceChildren();
  }
}
