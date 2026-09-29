/*
 * Replay controller: loads a diary file and steps through its moves.
 *
 * `current` is how many half-moves have been played on the board:
 * 0 = starting position, diary.moves.length = final position.
 */

class Replay {
  constructor(board, ui) {
    this.board = board;
    this.ui = ui;       // page elements the replay writes to
    this.diary = null;
    this.current = 0;
  }

  async load(file) {
    const response = await fetch(`games/${file}`);
    if (!response.ok) throw new Error(`Could not load games/${file}`);
    this.diary = await response.json();
    this.current = 0;
    this.board.setPosition(this.diary.start_fen);
    this.update();
  }

  get total() { return this.diary ? this.diary.moves.length : 0; }

  /* One move forward, sliding the pieces. */
  next() {
    if (!this.diary || this.current >= this.total) return;
    this.board.applyMove(this.diary.moves[this.current], true);
    this.current += 1;
    this.update();
  }

  /* One move back: redraw the position before the last move. */
  back() {
    if (this.current > 0) this.goTo(this.current - 1);
  }

  /* Jump to any point in the game. Going forward, every move is still played
     one by one (without sliding) so the "board matches diary" check really
     tests each move. Going back, the saved position is drawn directly. */
  goTo(target) {
    if (!this.diary) return;
    target = Math.max(0, Math.min(this.total, target));
    if (target < this.current) {
      this.board.setPosition(target === 0 ? this.diary.start_fen
                                           : this.diary.moves[target - 1].fen_after);
      this.current = target;
    }
    while (this.current < target) {
      this.board.applyMove(this.diary.moves[this.current], false);
      this.current += 1;
    }
    this.update();
  }

  /* The position the diary says should be on the board right now. */
  expectedFen() {
    return this.current === 0 ? this.diary.start_fen
                              : this.diary.moves[this.current - 1].fen_after;
  }

  /* Refreshes the text around the board. */
  update() {
    const d = this.diary;
    const m = this.current > 0 ? d.moves[this.current - 1] : null;

    this.ui.players.textContent = `${d.white.name} (White) vs ${d.black.name} (Black)`;
    this.ui.counter.textContent = `Half-move ${this.current} of ${this.total}`;

    if (m) {
      const dots = m.color === "white" ? "." : "...";
      this.ui.move.textContent = `${m.move_number}${dots} ${m.san}`;
      this.ui.thought.textContent = m.thought;
      this.ui.who.textContent = m.color === "white" ? d.white.name : d.black.name;
    } else {
      this.ui.move.textContent = "Start";
      this.ui.thought.textContent = "";
      this.ui.who.textContent = "";
    }

    this.ui.result.textContent = this.current === this.total ? d.result_text : "";

    const ok = this.board.matchesFen(this.expectedFen());
    this.ui.check.textContent = ok ? "✓ Board matches diary" : "✗ Board does NOT match diary";
    this.ui.check.className = ok ? "check ok" : "check bad";

    if (this.onChange) this.onChange();  // e.g. re-evaluate the new position
  }
}

/* Self-test: plays every game from start to finish, move by move, and checks
   the board after each move. Open the page with ?check at the end of the
   address to run it. */
async function runSelfTest(board, gamesList) {
  const lines = [];
  let failures = 0;
  for (const g of gamesList) {
    const diary = await (await fetch(`games/${g.file}`)).json();
    board.setPosition(diary.start_fen);
    let problem = null;
    for (let i = 0; i < diary.moves.length && !problem; i++) {
      const m = diary.moves[i];
      try {
        board.applyMove(m, false);
        if (!board.matchesFen(m.fen_after)) problem = `mismatch after half-move ${i + 1} (${m.san})`;
      } catch (err) {
        problem = `error at half-move ${i + 1} (${m.san}): ${err.message}`;
      }
    }
    if (problem) failures += 1;
    lines.push(`${problem ? "FAIL" : "PASS"}  ${g.file}  (${diary.moves.length} half-moves)` +
               (problem ? `  -> ${problem}` : ""));
  }
  lines.push(failures ? `${failures} GAME(S) FAILED` : "ALL GAMES PASSED");
  return lines.join("\n");
}

/* Plays the game by itself, one move at a time. Moves with a longer thought
   stay on screen longer so there is time to read the speech bubble. */
class Autoplay {
  constructor(replay, onStateChange) {
    this.replay = replay;
    this.onStateChange = onStateChange;  // told when playing starts or stops
    this.speed = 1;
    this.timer = null;
  }

  get playing() { return this.timer !== null; }

  toggle() { this.playing ? this.stop() : this.start(); }

  start() {
    if (!this.replay.diary) return;
    if (this.replay.current >= this.replay.total) this.replay.goTo(0);  // replay from the start
    this.timer = setTimeout(() => this.step(), 400);
    this.onStateChange(true);
  }

  stop() {
    if (!this.playing) return;
    clearTimeout(this.timer);
    this.timer = null;
    this.onStateChange(false);
  }

  step() {
    this.replay.next();
    if (this.replay.current >= this.replay.total) { this.stop(); return; }
    this.timer = setTimeout(() => this.step(), this.delay());
  }

  /* Milliseconds to wait before the next move. */
  delay() {
    const m = this.replay.diary.moves[this.replay.current - 1];
    const hasBubble = m && m.thought_source !== "move_description";
    const reading = hasBubble ? Math.min(m.thought.length * 30, 4500) : 0;
    return (900 + reading) / this.speed;
  }
}

/* The list of moves beside the board, in two columns (White, Black).
   Clicking a move jumps there. */
class MoveList {
  constructor(element, onPick) {
    this.el = element;
    this.onPick = onPick;
    this.cells = [];
  }

  build(diary) {
    this.el.replaceChildren();
    this.cells = [];
    let row = null;
    diary.moves.forEach((m, i) => {
      if (m.color === "white" || row === null) {
        row = document.createElement("div");
        row.className = "ml-row";
        row.innerHTML = `<span class="ml-num">${m.move_number}.</span>`;
        this.el.appendChild(row);
        if (m.color === "black") row.appendChild(this.cell("…", null));  // game starts with Black
      }
      row.appendChild(this.cell(m.san, i + 1));
    });
  }

  cell(text, ply) {
    const button = document.createElement("button");
    button.className = "ml-move";
    button.textContent = text;
    if (ply === null) { button.disabled = true; return button; }
    button.onclick = () => this.onPick(ply);
    this.cells[ply] = button;
    return button;
  }

  /* Marks the current move and scrolls the list so it is visible. */
  setCurrent(ply) {
    this.el.querySelectorAll(".ml-move.current").forEach((b) => b.classList.remove("current"));
    const cell = this.cells[ply];
    if (!cell) { this.el.scrollTop = 0; return; }
    cell.classList.add("current");
    const row = cell.parentElement;
    const top = row.offsetTop;  // the list is the reference point (position: relative)
    if (top < this.el.scrollTop || top + row.offsetHeight > this.el.scrollTop + this.el.clientHeight) {
      this.el.scrollTop = top - this.el.clientHeight / 2;
    }
  }
}
