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
