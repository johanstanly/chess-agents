/*
 * Talks to Stockfish (a free chess engine running inside the browser) and
 * draws the evaluation bar. No AI service is used; this costs nothing.
 *
 * Scores are always given from White's point of view:
 *   { cp: 120 }                  White is 1.2 pawns better
 *   { mate: 3, whiteWins: true } White can force checkmate in 3 moves
 */

class Engine {
  constructor(path = "engine/stockfish-18-lite-single.js", maxDepth = 18) {
    this.maxDepth = maxDepth;
    this.worker = new Worker(path);
    this.worker.onmessage = (e) => this.onLine(String(e.data));
    this.searching = false;
    this.current = null;  // the position being analysed now
    this.pending = null;  // the next position to analyse
    this.worker.postMessage("uci");
    this.worker.postMessage("ucinewgame");
    this.worker.postMessage("isready");
  }

  /* Starts analysing a position. onUpdate(info) is called each time the
     engine looks one step deeper: { score, depth, bestMoveUci }. */
  analyse(fen, onUpdate) {
    this.pending = { fen, onUpdate };
    if (this.searching) this.worker.postMessage("stop");  // finish the old one first
    else this.startPending();
  }

  startPending() {
    if (!this.pending) return;
    this.current = this.pending;
    this.pending = null;
    this.searching = true;
    this.worker.postMessage(`position fen ${this.current.fen}`);
    this.worker.postMessage(`go depth ${this.maxDepth}`);
  }

  onLine(line) {
    if (line.startsWith("bestmove")) {
      this.searching = false;
      this.startPending();
      return;
    }
    if (!line.startsWith("info") || !line.includes(" score ") || this.pending) return;

    const words = line.split(" ");
    const read = (key) => words[words.indexOf(key) + 1];
    const whiteToMove = this.current.fen.split(" ")[1] === "w";
    let score;
    if (words.includes("mate")) {
      const n = Number(read("mate"));
      // Stockfish scores from the side to move; "mate 0" means already checkmated.
      const sideToMoveWins = n > 0;
      score = { mate: Math.abs(n), whiteWins: n === 0 ? !whiteToMove : sideToMoveWins === whiteToMove };
    } else {
      const cp = Number(read("cp"));
      score = { cp: whiteToMove ? cp : -cp };
    }
    const bestMoveUci = words.includes("pv") ? read("pv") : null;
    this.current.onUpdate({ score, depth: Number(read("depth")), bestMoveUci });
  }
}

/* How much of the bar is White, from 0 to 100 (same curve Lichess uses). */
function whiteShare(score) {
  if (score.mate !== undefined) return score.whiteWins ? 100 : 0;
  const share = 50 + 50 * (2 / (1 + Math.exp(-0.00368208 * score.cp)) - 1);
  return Math.max(4, Math.min(96, share));
}

/* Short text for a score: "+1.2", "-0.4", "M3". */
function scoreText(score) {
  if (score.mate !== undefined) {
    if (score.mate === 0) return score.whiteWins ? "1-0" : "0-1";
    return (score.whiteWins ? "" : "-") + `M${score.mate}`;  // -M3: Black mates in 3
  }
  const pawns = score.cp / 100;
  return (pawns > 0 ? "+" : "") + pawns.toFixed(1);
}

class EvalBar {
  constructor(element) {
    this.el = element;
    this.fill = element.querySelector(".eval-fill");
    this.label = element.querySelector(".eval-label");
    this.show({ cp: 0 });
  }

  show(score) {
    const share = whiteShare(score);
    this.fill.style.height = share + "%";
    const whiteAhead = score.mate !== undefined ? score.whiteWins : score.cp >= 0;
    this.label.textContent = scoreText(score).replace(/^[+-]/, "");
    // The number sits at White's end when White is ahead, Black's end otherwise.
    this.label.className = "eval-label " + (whiteAhead ? "at-white" : "at-black");
  }

  setFlipped(flipped) {
    this.el.classList.toggle("flipped", flipped);
  }
}
