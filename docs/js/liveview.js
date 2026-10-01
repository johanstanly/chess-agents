/*
 * Drives the live page: the 3D room (scene3d.js) and the side panel (our 2D
 * board, evaluation bar, captured pieces, move list and game review) together.
 *
 * Two ways to follow a game:
 *  - LIVE: while a game runs on this computer, arena/live.py keeps
 *    live/status.json up to date; we read it about once a second.
 *  - REAL SPEED: a finished game replayed at the pace it was played. Each
 *    move shows "…" for the time the player really thought, then the thought
 *    is typed out, then the move is played.
 */

const POLL_MS = 1000;
const STALE_MINUTES = 15;      // a status file this old without "finished" is from a crashed run
// How long each move stays on screen: about 5 seconds in all (typing the thought,
// reading it, moving the piece), a little more only for long thoughts. The game
// runner uses the same rule (arena/live.py, viewing_seconds).
const TYPE_SPEED = 40;         // letters per second
const MOVE_SECONDS = 1.2;      // the piece being picked up and put down
const VIEW_SECONDS = 5;        // the whole move
const MIN_READ = 1.5;          // reading time left after even a long thought is typed
const typingSeconds = (text) => text.length / TYPE_SPEED;
const readingSeconds = (text) => Math.max(MIN_READ, VIEW_SECONDS - MOVE_SECONDS - typingSeconds(text));
const sleep = (ms) => new Promise((r) => setTimeout(r, ms));

export class LiveView {
  constructor(room, panel) {
    this.room = room;
    this.p = panel;            // { board, evalBar, bars, moveList, engine, resultCard, el: {...} }
    this.diary = null;
    this.shown = 0;            // how many moves are on the 2D board
    this.mode = null;          // "live" or "replay"
    this.run = 0;              // increases on every new game, so old timers stop
  }

  // ---------- Loading a game ----------
  async fetchDiary(file) {
    const r = await fetch(`games/${file}?t=${Date.now()}`, { cache: "no-store" });
    if (!r.ok) throw new Error(`Could not load games/${file}`);
    return r.json();
  }

  /* Shows a game from its start (or up to `upto` moves), ready to play on. */
  async loadGame(d, upto = 0) {
    this.diary = d;
    const title = `${d.white.name} vs ${d.black.name}`;
    this.p.el.title.textContent = title;
    document.title = `${title} · Live`;
    await this.room.setPlayers(d.white.name, d.black.name);
    this.shown = 0;
    this.p.board.setPosition(d.start_fen);
    this.p.moveList.build({ moves: d.moves.slice(0, upto) });
    this.room.reset();
    this.p.resultCard.reset();
    this.showReview(null);
    this.p.el.players.textContent = `${d.white.name} (White) vs ${d.black.name} (Black)`;
    this.goTo(upto);
  }

  /* Puts the 2D board and the little 3D board at move `ply`, without animation. */
  goTo(ply) {
    const d = this.diary;
    this.p.board.setPosition(ply === 0 ? d.start_fen : d.moves[ply - 1].fen_after);
    this.shown = ply;
    this.afterMove(false);
  }

  /* Plays the next move. With `animate`, the player first picks up the piece and
     carries it on the little 3D board; the 2D board moves when the piece lands.
     Resolves to false if something else took over in the meantime. */
  async playNext(animate = false) {
    const m = this.diary.moves[this.shown];
    const run = this.run, at = this.shown;
    if (animate) {
      await this.room.moved(m.color, m);
      if (run !== this.run || at !== this.shown) return false;
    } else {
      this.room.moved(m.color);
    }
    this.p.board.applyMove(m, true);
    this.shown += 1;
    this.afterMove(true);
    return true;
  }

  afterMove(rebuildList) {
    const d = this.diary;
    const m = this.shown > 0 ? d.moves[this.shown - 1] : null;
    const fen = m ? m.fen_after : d.start_fen;
    this.room.setPosition(fen);
    const toMove = fen.split(" ")[1];
    this.p.board.setHighlights(m ? { from: m.from, to: m.to } : null,
                              m && m.check ? this.p.board.findKing(toMove) : null);
    if (rebuildList || this.p.moveList.cells.length <= this.shown) {
      this.p.moveList.build({ moves: d.moves.slice(0, Math.max(this.shown, this.listed || 0)) });
    }
    this.p.moveList.setCurrent(this.shown);
    this.p.bars.update(this.p.board, { white: d.white.name, black: d.black.name });
    this.p.el.counter.textContent = m ? `Move ${m.move_number}${m.color === "white" ? "." : "..."} ${m.san}`
                                      : "Start position";
    if (this.p.engine) {
      this.p.engine.analyse(fen, ({ score }) => this.p.evalBar.show(score));
    }
  }

  showEnd() {
    const d = this.diary;
    if (d.result === "*") return;
    this.room.finish(d.result);
    const last = d.moves[d.moves.length - 1];
    this.p.resultCard.show(d.result_text, `${d.result} · ${Math.ceil(d.moves.length / 2)} moves`,
                           last ? this.p.board.squareCell(last.to).row : 4);
    this.p.el.status.textContent = d.result_text;
    this.showReview(d.review ? d : null);
  }

  /* The game review card: accuracy and ?! ? ?? counts, once Stockfish has graded the game. */
  showReview(d) {
    const card = this.p.el.reviewCard;
    card.hidden = !d;
    if (!d) return;
    this.p.moveList.build({ moves: d.moves });   // now with the grade marks
    this.p.moveList.setCurrent(this.shown);
    const rows = ["white", "black"].map((color) => {
      const r = d.review[color];
      const row = document.createElement("div");
      row.className = "review-row";
      row.innerHTML = `<img alt="" src="pieces/${color[0]}K.svg"><span class="review-name"></span>` +
        `<span class="review-acc">${r.accuracy.toFixed(1)}%</span>` +
        `<span class="review-counts"><b class="inaccuracy">?! ${r.inaccuracies}</b>` +
        `<b class="mistake">? ${r.mistakes}</b><b class="blunder">?? ${r.blunders}</b></span>`;
      row.querySelector(".review-name").textContent = d[color].name;
      return row;
    });
    this.p.el.reviewRows.replaceChildren(...rows);
  }

  stop() { this.run += 1; clearTimeout(this.timer); }

  // ---------- LIVE: follow a game being played right now ----------
  async startLive() {
    this.stop();
    this.mode = "live";
    const run = this.run;
    this.lastSeq = null;
    const poll = async () => {
      if (run !== this.run) return;
      try { await this.checkLive(); } catch (err) { /* the file may be mid-update: try again */ }
      if (run === this.run) this.timer = setTimeout(poll, POLL_MS);
    };
    poll();
  }

  /* Reads the live status; returns it (or null when no game is running). */
  static async readStatus() {
    try {
      const r = await fetch(`live/status.json?t=${Date.now()}`, { cache: "no-store" });
      if (!r.ok) return null;
      const s = await r.json();
      const ageMinutes = (Date.now() - new Date(s.updated).getTime()) / 60000;
      return s.state !== "finished" && ageMinutes > STALE_MINUTES ? null : s;
    } catch { return null; }
  }

  async checkLive() {
    const s = await LiveView.readStatus();
    if (!s) { this.p.el.status.textContent = "No game is being played right now."; return; }
    if (s.seq === this.lastSeq) return;
    this.lastSeq = s.seq;

    // A new game (or the page was just opened): catch up with what was played so far.
    if (!this.diary || this.diary.id !== s.game_id) {
      const d = await this.fetchDiary(s.file);
      await this.loadGame(d, d.moves.length);
      this.listed = d.moves.length;
    }
    // New moves since last time: play them on the boards.
    if (s.ply > this.shown || (s.state === "finished" && s.graded && !this.diary.review)) {
      const d = await this.fetchDiary(s.file);
      this.diary = d;
      this.listed = d.moves.length;
      // Catching up is instant; the newest move is shown properly: its thought is
      // typed out and given time to be read, then the piece is moved by hand.
      while (this.shown < d.moves.length) {
        if (this.shown < d.moves.length - 1) await this.playNext(false);
        else await this.thinkAloudThenMove(d.moves[this.shown]);
      }
    }
    const who = s.player || "";
    if (s.state === "thinking") {
      this.room.think(s.color);
      this.p.el.status.textContent = `● LIVE · ${who} is thinking…`;
    } else if (s.state === "writing") {
      this.room.say(s.color, s.thought);
      this.p.el.status.textContent = `● LIVE · ${who} is writing his thought…`;
    } else if (s.state === "moved") {
      this.room.say(s.color, s.thought);
      this.p.el.status.textContent = `● LIVE · ${who} played ${s.san}`;
    } else if (s.state === "finished") {
      this.showEnd();
      this.p.el.status.textContent = `${s.result_text}${s.graded ? "" : " · Stockfish is grading the game…"}`;
    } else if (s.state === "stopped") {
      this.p.el.status.textContent = `The game paused: ${s.message} It will continue when the runner is restarted.`;
    }
  }

  /* Types the move's thought, leaves it up long enough to read, then plays the move. */
  async thinkAloudThenMove(m) {
    const run = this.run;
    if (m.thought_source !== "move_description") {
      this.room.say(m.color, m.thought);
      await this.room.whenTyped(m.color);
      await sleep(readingSeconds(m.thought) * 1000 / this.room.speed);
      if (run !== this.run) return false;
    }
    return this.playNext(true);
  }

  // ---------- REAL SPEED: replay a finished game at the pace it was played ----------
  async startReplay(d, from = 0) {
    this.stop();
    const run = this.run;
    this.mode = "replay";
    this.listed = 0;   // the move list grows as the game is played: no spoilers
    if (this.diary !== d) await this.loadGame(d, from);
    else this.goTo(from);
    if (run !== this.run) return;   // another game was chosen while this one loaded
    this.paused = false;
    this.step(run);
  }

  /* How long the player really thought about move m, in seconds. */
  thinkingTime(m, i) {
    if (m.usage && m.usage.seconds) return m.usage.seconds;
    const prev = this.diary.moves[i - 1];
    if (m.time && prev && prev.time) return Math.max(0.5, (new Date(m.time) - new Date(prev.time)) / 1000);
    return 2;   // famous sample games have no timing: a calm default
  }

  step(run) {
    const d = this.diary;
    const wait = (seconds, next) => { this.timer = setTimeout(() => run === this.run && next(), seconds * 1000 / this.room.speed); };
    if (this.paused) return;
    if (this.shown >= d.moves.length) { this.showEnd(); this.onReplayState?.(false); return; }
    const m = d.moves[this.shown];
    const name = d[m.color].name;
    this.onReplayState?.(true);
    this.room.think(m.color);
    this.p.el.status.textContent = `▶ ${name} is thinking… (real speed${this.room.speed > 1 ? ` ×${this.room.speed}` : ""})`;
    wait(this.thinkingTime(m, this.shown), () => {
      this.thinkAloudThenMove(m).then((played) => {
        if (!played || run !== this.run) return;
        this.p.el.status.textContent = `▶ ${name} played ${m.san}`;
        wait(0.8, () => this.step(run));
      });
    });
  }

  pause() { this.paused = true; this.stop(); this.onReplayState?.(false); }
  resume() { if (this.diary && this.mode === "replay") this.startReplay(this.diary, this.shown); }
}
