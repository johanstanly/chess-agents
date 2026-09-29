/*
 * The player bars above and below the board: name, the pieces that player
 * has captured, and how many points they are ahead (pawn 1, knight 3,
 * bishop 3, rook 5, queen 9), like on chess.com.
 * Everything is worked out from the pieces currently on the board, so it
 * also works in analysis mode.
 */

const PIECE_VALUES = { P: 1, N: 3, B: 3, R: 5, Q: 9 };
const START_COUNTS = { P: 8, N: 2, B: 2, R: 2, Q: 1 };

/* Counts each colour's pieces: { w: {P: 8, ...}, b: {...} }. */
function countPieces(placement) {
  const counts = { w: { P: 0, N: 0, B: 0, R: 0, Q: 0 }, b: { P: 0, N: 0, B: 0, R: 0, Q: 0 } };
  for (const code of Object.values(placement)) {
    if (code[1] !== "K") counts[code[0]][code[1]] += 1;
  }
  return counts;
}

/* The pieces of `color` that are no longer on the board (i.e. were captured).
   A promoted pawn is not counted as captured: extra queens, rooks etc.
   beyond the starting number must have come from pawns. */
function missingPieces(count) {
  const missing = {};
  let promoted = 0;
  for (const type of ["N", "B", "R", "Q"]) {
    missing[type] = Math.max(0, START_COUNTS[type] - count[type]);
    promoted += Math.max(0, count[type] - START_COUNTS[type]);
  }
  missing.P = Math.max(0, START_COUNTS.P - count.P - promoted);
  return missing;
}

function materialPoints(count) {
  return Object.entries(count).reduce((sum, [type, n]) => sum + PIECE_VALUES[type] * n, 0);
}

class PlayerBars {
  constructor(topEl, bottomEl) {
    this.top = topEl;
    this.bottom = bottomEl;
  }

  /* names = { white: "Claude A", black: "Claude B" } */
  update(board, names) {
    const counts = countPieces(board.currentPlacement());
    const lead = materialPoints(counts.w) - materialPoints(counts.b);
    // White captured Black's missing pieces, and the other way round.
    const white = { name: names.white, color: "w", captured: missingPieces(counts.b), capturedColor: "b",
                    lead: lead > 0 ? lead : 0 };
    const black = { name: names.black, color: "b", captured: missingPieces(counts.w), capturedColor: "w",
                    lead: lead < 0 ? -lead : 0 };
    const [topPlayer, bottomPlayer] = board.flipped ? [white, black] : [black, white];
    this.render(this.top, topPlayer);
    this.render(this.bottom, bottomPlayer);
  }

  render(el, p) {
    const groups = ["P", "N", "B", "R", "Q"]
      .filter((type) => p.captured[type] > 0)
      .map((type) => {
        const icons = Array.from({ length: p.captured[type] },
          () => `<img src="pieces/${p.capturedColor}${type}.svg" alt="">`).join("");
        return `<span class="cap-group" title="${p.captured[type]} × ${type}">${icons}</span>`;
      }).join("");
    el.innerHTML =
      `<img class="bar-king" src="pieces/${p.color}K.svg" alt="">` +
      `<span class="bar-name"></span>` +
      `<span class="captured">${groups}</span>` +
      (p.lead ? `<span class="lead">+${p.lead}</span>` : "");
    el.querySelector(".bar-name").textContent = p.name;  // names are shown as plain text
    el.dataset.color = p.color;
  }
}
