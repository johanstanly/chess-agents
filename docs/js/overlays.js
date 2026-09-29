/*
 * Things drawn on top of the board:
 *  - ThoughtBubble: a speech bubble pointing at the piece that just moved,
 *    showing what the player was thinking.
 *  - ResultCard: the result shown in the middle of the board at the end.
 */

class ThoughtBubble {
  constructor(board) {
    this.board = board;
    this.square = null;
    this.el = document.createElement("div");
    this.el.className = "bubble";
    this.el.innerHTML = '<div class="bubble-head"></div><div class="bubble-text"></div><div class="bubble-tail"></div>';
    board.board.appendChild(this.el);
    board.flipListeners.push(() => { if (this.square) this.place(); });
  }

  /* Shows `text` in a bubble pointing at `square`. `side` is "white"/"black". */
  show(square, head, text, side) {
    this.square = square;
    this.el.querySelector(".bubble-head").textContent = head;
    this.el.querySelector(".bubble-text").textContent = text;
    this.el.dataset.side = side;
    this.place();
    this.el.classList.remove("visible");
    void this.el.offsetWidth;            // restart the fade-in animation
    this.el.classList.add("visible");
  }

  hide() {
    this.square = null;
    this.el.classList.remove("visible");
  }

  /* Bubble below the square if the square is in the top half of the board,
     above it otherwise, and kept inside the board's edges. */
  place() {
    const WIDTH = 50;                    // bubble width, % of the board
    const { col, row } = this.board.squareCell(this.square);
    const centre = col * 12.5 + 6.25;
    const left = Math.max(1, Math.min(99 - WIDTH, centre - WIDTH / 2));
    const s = this.el.style;
    s.width = WIDTH + "%";
    s.left = left + "%";
    if (row < 4) {
      s.top = (row + 1) * 12.5 + 1 + "%";
      s.bottom = "auto";
      this.el.classList.add("below");
    } else {
      s.bottom = (8 - row) * 12.5 + 1 + "%";
      s.top = "auto";
      this.el.classList.remove("below");
    }
    this.el.querySelector(".bubble-tail").style.left = ((centre - left) / WIDTH) * 100 + "%";
  }
}

class ResultCard {
  constructor(board) {
    this.el = document.createElement("div");
    this.el.className = "result-card";
    this.el.innerHTML = '<div class="result-title"></div><div class="result-sub"></div><div class="result-hint">click to close</div>';
    this.el.addEventListener("pointerdown", (e) => { e.stopPropagation(); this.dismissed = true; this.hide(); });
    board.board.appendChild(this.el);
    this.dismissed = false;
  }

  /* `awayFromRow` (0-7 from the top) is where the last move landed: the card
     goes to the other end of the board so it does not cover the speech bubble. */
  show(title, sub, awayFromRow = 4) {
    if (this.dismissed) return;
    this.el.querySelector(".result-title").textContent = title;
    this.el.querySelector(".result-sub").textContent = sub;
    this.el.classList.toggle("at-top", awayFromRow >= 4);
    this.el.classList.toggle("at-bottom", awayFromRow < 4);
    this.el.classList.add("visible");
  }

  hide() { this.el.classList.remove("visible"); }

  /* A new game shows its card again even if the last one was closed. */
  reset() { this.dismissed = false; this.hide(); }
}

/* Arrows and circles drawn with the right mouse button, like on chess.com:
   right-drag from one square to another draws an arrow (L-shaped for a
   knight's jump), right-click on one square circles it. Doing the same again
   removes it. A left click, or any change of position, clears them all. */
class ArrowLayer {
  constructor(board) {
    this.board = board;
    this.marks = [];         // { from, to } for arrows; from === to for circles
    this.start = null;       // square where a right-drag began
    this.svg = document.createElementNS("http://www.w3.org/2000/svg", "svg");
    this.svg.setAttribute("class", "arrows");
    this.svg.setAttribute("viewBox", "0 0 8 8");
    board.board.appendChild(this.svg);
    board.flipListeners.push(() => this.draw());

    const el = board.board;
    el.addEventListener("contextmenu", (e) => e.preventDefault());  // no browser menu
    el.addEventListener("pointerdown", (e) => {
      if (e.button === 2) {
        this.start = this.squareAt(e);
      } else if (e.button === 0) {
        this.clear();
      }
    });
    el.addEventListener("pointerup", (e) => {
      if (e.button !== 2 || !this.start) return;
      const end = this.squareAt(e);
      if (end) this.toggle(this.start, end);
      this.start = null;
    });
  }

  squareAt(e) {
    const r = this.board.board.getBoundingClientRect();
    let col = Math.floor(((e.clientX - r.left) / r.width) * 8);
    let row = Math.floor(((e.clientY - r.top) / r.height) * 8);
    if (col < 0 || col > 7 || row < 0 || row > 7) return null;
    if (this.board.flipped) { col = 7 - col; row = 7 - row; }
    return "abcdefgh"[col] + (8 - row);
  }

  toggle(from, to) {
    const i = this.marks.findIndex((m) => m.from === from && m.to === to);
    if (i >= 0) this.marks.splice(i, 1);
    else this.marks.push({ from, to });
    this.draw();
  }

  clear() {
    if (!this.marks.length) return;
    this.marks = [];
    this.draw();
  }

  /* Centre of a square in board units (the board is 8 x 8). */
  centre(square) {
    const { col, row } = this.board.squareCell(square);
    return [col + 0.5, row + 0.5];
  }

  draw() {
    const parts = [];
    for (const { from, to } of this.marks) {
      const [x1, y1] = this.centre(from);
      const [x2, y2] = this.centre(to);
      if (from === to) {
        parts.push(`<circle cx="${x1}" cy="${y1}" r="0.45" class="circle-mark"/>`);
        continue;
      }
      const dx = x2 - x1, dy = y2 - y1;
      const knight = (Math.abs(dx) === 1 && Math.abs(dy) === 2) || (Math.abs(dx) === 2 && Math.abs(dy) === 1);
      // Knight jumps bend: first along the longer side, then the shorter one.
      const points = knight
        ? [[x1, y1], Math.abs(dy) > Math.abs(dx) ? [x1, y2] : [x2, y1], [x2, y2]]
        : [[x1, y1], [x2, y2]];
      parts.push(this.arrowPath(points));
    }
    this.svg.innerHTML = parts.join("");
  }

  /* A line through `points` ending in an arrow head at the last point. */
  arrowPath(points) {
    const HEAD = 0.42, WIDTH = 0.17, HEAD_WIDTH = 0.5;
    const [px, py] = points[points.length - 2];
    const [ex, ey] = points[points.length - 1];
    const len = Math.hypot(ex - px, ey - py);
    const ux = (ex - px) / len, uy = (ey - py) / len;
    // Stop the line where the head starts, and start it a little off-centre.
    const baseX = ex - ux * HEAD, baseY = ey - uy * HEAD;
    const line = points.slice(0, -1).map(([x, y]) => `${x},${y}`);
    const [sx, sy] = points[0];
    const [nx, ny] = points[1];
    const sl = Math.hypot(nx - sx, ny - sy);
    line[0] = `${sx + ((nx - sx) / sl) * 0.2},${sy + ((ny - sy) / sl) * 0.2}`;
    line.push(`${baseX},${baseY}`);
    const hx = -uy * HEAD_WIDTH / 2, hy = ux * HEAD_WIDTH / 2;
    return `<polyline points="${line.join(" ")}" class="arrow-line" stroke-width="${WIDTH}"/>` +
      `<polygon points="${ex - ux * 0.08},${ey - uy * 0.08} ${baseX + hx},${baseY + hy} ${baseX - hx},${baseY - hy}" class="arrow-head"/>`;
  }
}
