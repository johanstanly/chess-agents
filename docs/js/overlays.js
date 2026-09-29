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
    board.onFlip = () => { if (this.square) this.place(); };
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
