// The results page: reads data/results.json (written by arena/experiment.py) and draws
// the headline numbers, four charts, Magnus's final notebook and the table of games.
// The charts are plain SVG, redrawn when the window is resized.

(() => {
  const $ = (id) => document.getElementById(id);
  const SVGNS = "http://www.w3.org/2000/svg";
  const css = getComputedStyle(document.querySelector(".results-page"));
  const COLOR = { magnus: css.getPropertyValue("--magnus").trim(), hans: css.getPropertyValue("--hans").trim() };
  const NAME = { magnus: "Magnus", hans: "Hans" };

  // Version 1 (Sonnet, low effort, simpler notebook) is archived outside the site;
  // these are its 10 Magnus vs Hans games, from experiments/v1/docs/data/results.json.
  const V1 = { magnusPoints: 4.5, games: 10, magnusAccuracy: 67.8, hansAccuracy: 66.8 };

  const SHORT = {
    "Ruy Lopez": "Ruy Lopez", "Italian Game": "Italian", "Sicilian Defence, Najdorf": "Sicilian",
    "French Defence": "French", "Caro-Kann Defence": "Caro-Kann", "Queen's Gambit Declined": "QGD",
  };

  // ---------- Reading the results ----------

  const side = (g, who) => (g.white === who ? "white" : g.black === who ? "black" : null);
  const acc = (g, who) => (side(g, who) ? g[`${side(g, who)}_accuracy`] : null);
  const blunders = (g, who) => (side(g, who) ? g[`${side(g, who)}_blunders`] : null);
  const avg = (xs) => xs.reduce((a, b) => a + b, 0) / xs.length;
  const half = (x) => (Number.isInteger(x) ? String(x) : `${Math.floor(x) || ""}½`);
  const pct = (x) => `${x.toFixed(1)}%`;

  function winner(g) {
    if (g.result === "1-0") return g.white;
    if (g.result === "0-1") return g.black;
    return null;
  }
  function resultWords(g) {
    const w = winner(g);
    return w ? `${w.replace(" (skill 0)", "")} won` : "Draw";
  }

  // ---------- Small helpers for drawing ----------

  function el(name, attrs = {}, parent) {
    const node = document.createElementNS(SVGNS, name);
    for (const [k, v] of Object.entries(attrs)) node.setAttribute(k, v);
    if (parent) parent.appendChild(node);
    return node;
  }

  const tooltip = $("tooltip");
  function showTip(evt, html) {
    tooltip.innerHTML = html;
    tooltip.hidden = false;
    const pad = 14, w = tooltip.offsetWidth, h = tooltip.offsetHeight;
    let x = evt.clientX + pad, y = evt.clientY + pad;
    if (x + w > innerWidth - 8) x = evt.clientX - w - pad;
    if (y + h > innerHeight - 8) y = evt.clientY - h - pad;
    tooltip.style.left = `${x}px`;
    tooltip.style.top = `${y}px`;
  }
  const hideTip = () => { tooltip.hidden = true; };
  const tipRow = (key, text) => `<div class="row"><i style="background:${COLOR[key]}"></i>${text}</div>`;

  // A dot with a bigger invisible circle around it, so it is easy to hover.
  function dot(g, x, y, color, html) {
    const hit = el("circle", { cx: x, cy: y, r: 12, class: "hit" }, g);
    const d = el("circle", { cx: x, cy: y, r: 4.5, fill: color, class: "dot" }, g);
    hit.addEventListener("mousemove", (e) => { d.classList.add("on"); showTip(e, html); });
    hit.addEventListener("mouseleave", () => { d.classList.remove("on"); hideTip(); });
  }

  // A line chart over named steps (games or checkpoints), one line per player, with
  // the last value labelled at the right end of each line.
  function lineChart(box, { labels, sublabels = [], series, yMin, yMax, yStep, yFmt, tip, endFmt, height = 300 }) {
    const W = Math.max(320, box.clientWidth), H = height;
    const m = { top: 12, right: 92, bottom: sublabels.length ? 44 : 28, left: 44 };
    const x = (i) => m.left + (labels.length === 1 ? 0 : (i / (labels.length - 1)) * (W - m.left - m.right));
    const y = (v) => m.top + (1 - (v - yMin) / (yMax - yMin)) * (H - m.top - m.bottom);
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });

    for (let v = yMin; v <= yMax + 1e-9; v += yStep) {
      el("line", { x1: m.left, x2: W - m.right + 8, y1: y(v), y2: y(v), class: v === yMin ? "axis" : "grid" }, svg);
      el("text", { x: m.left - 8, y: y(v) + 4, "text-anchor": "end" }, svg).textContent = yFmt(v);
    }
    labels.forEach((lab, i) => {
      el("text", { x: x(i), y: H - m.bottom + 18, "text-anchor": "middle" }, svg).textContent = lab;
      if (sublabels[i]) el("text", { x: x(i), y: H - m.bottom + 34, "text-anchor": "middle" }, svg).textContent = sublabels[i];
    });

    // End labels: nudge apart if the two lines finish close together.
    const ends = series.map((s) => ({ s, y: y(s.values[s.values.length - 1]) }));
    if (ends.length === 2 && Math.abs(ends[0].y - ends[1].y) < 16) {
      const mid = (ends[0].y + ends[1].y) / 2, up = ends[0].y <= ends[1].y ? 0 : 1;
      ends[up].y = mid - 8; ends[1 - up].y = mid + 8;
    }

    for (const s of series) {
      const pts = s.values.map((v, i) => `${x(i)},${y(v)}`).join(" ");
      el("polyline", { points: pts, class: "line", stroke: COLOR[s.key] }, svg);
    }
    for (const s of series) {
      const g = el("g", {}, svg);
      s.values.forEach((v, i) => dot(g, x(i), y(v), COLOR[s.key], tip(i, s.key)));
    }
    for (const { s, y: ly } of ends) {
      const last = s.values[s.values.length - 1];
      el("text", { x: W - m.right + 14, y: ly + 4, class: "label-strong" }, svg)
        .textContent = `${NAME[s.key]} ${endFmt(last)}`;
    }
    box.replaceChildren(svg);
  }

  // A dumbbell chart: one row per opening, a dot for each player, joined by a line.
  function dumbbell(box, rows) {
    const W = Math.max(320, box.clientWidth), rowH = 40;
    const m = { top: 8, right: 20, bottom: 28, left: 92 };
    const H = m.top + rows.length * rowH + m.bottom;
    const xMin = 40, xMax = 100;
    const x = (v) => m.left + ((v - xMin) / (xMax - xMin)) * (W - m.left - m.right);
    const svg = el("svg", { viewBox: `0 0 ${W} ${H}`, role: "img" });
    for (let v = xMin; v <= xMax; v += 10) {
      el("line", { x1: x(v), x2: x(v), y1: m.top, y2: H - m.bottom, class: v === xMin ? "axis" : "grid" }, svg);
      el("text", { x: x(v), y: H - m.bottom + 18, "text-anchor": "middle" }, svg).textContent = `${v}%`;
    }
    rows.forEach((r, i) => {
      const cy = m.top + i * rowH + rowH / 2;
      if (r.highlight) el("rect", { x: 0, y: cy - rowH / 2 + 2, width: W, height: rowH - 4, rx: 6, class: "band" }, svg);
      el("text", { x: m.left - 10, y: cy + 4, "text-anchor": "end", class: r.highlight ? "label-strong" : "" }, svg)
        .textContent = r.label;
      el("line", { x1: x(Math.min(r.magnus, r.hans)), x2: x(Math.max(r.magnus, r.hans)), y1: cy, y2: cy,
                   stroke: "rgba(255,255,255,0.18)", "stroke-width": 2 }, svg);
      const g = el("g", {}, svg);
      for (const key of ["hans", "magnus"]) {
        dot(g, x(r[key]), cy, COLOR[key],
            `<b>${r.name}</b><br>${tipRow(key, `${NAME[key]}: ${pct(r[key])} average`)}` +
            `<div class="dim">${r.games.map((t) => t[key]).join("<br>")}</div>`);
      }
    });
    box.replaceChildren(svg);
  }

  // ---------- The page ----------

  function render(data, notebookText) {
    const games = data.games;
    const match = games.filter((g) => g.kind === "match").sort((a, b) => a.number - b.number);
    const checkpoints = games.filter((g) => g.kind === "yardstick");
    const cpNumbers = [...new Set(checkpoints.map((g) => g.checkpoint))].sort((a, b) => a - b);

    // Headline numbers.
    const magnusPoints = match.reduce((a, g) => a + g.magnus_score, 0);
    const hansPoints = match.length - magnusPoints;
    const mAcc = match.map((g) => acc(g, "Magnus")), hAcc = match.map((g) => acc(g, "Hans"));
    const higher = match.filter((g) => acc(g, "Magnus") > acc(g, "Hans")).length;
    const wins = match.filter((g) => winner(g) === "Magnus").length;
    const losses = match.filter((g) => winner(g) === "Hans").length;
    const draws = match.length - wins - losses;
    const tiles = [
      ["Final score, Magnus vs Hans", `${half(magnusPoints)} – ${half(hansPoints)}`,
       `${wins} wins, ${draws} draw${draws === 1 ? "" : "s"}, ${losses} losses for Magnus`],
      ["Average accuracy", `${avg(mAcc).toFixed(1)} vs ${avg(hAcc).toFixed(1)}`, "Magnus vs Hans, per game"],
      ["Games with the higher accuracy", `${higher} of ${match.length}`, "for Magnus"],
      ["Version 1, for comparison", `${half(V1.magnusPoints)} – ${half(V1.games - V1.magnusPoints)}`,
       `accuracy ${V1.magnusAccuracy} vs ${V1.hansAccuracy}: no difference`],
    ];
    $("tiles").innerHTML = tiles.map(([l, v, s]) =>
      `<div class="tile"><div class="label">${l}</div><div class="value">${v}</div><div class="sub">${s}</div></div>`).join("");

    // Legends.
    for (const lg of document.querySelectorAll(".legend")) {
      lg.innerHTML = lg.dataset.series.split(",").map((k) =>
        `<span><i style="background:${COLOR[k]}"></i>${NAME[k]}${k === "magnus" ? " (notebook)" : " (no notebook)"}</span>`).join("");
    }

    const gameTip = (g) => `<b>Game ${g.number}: ${g.white} vs ${g.black}</b><div class="dim">${g.opening} · ` +
      `${resultWords(g)} in ${g.moves} moves</div>`;

    // Running score.
    let ms = 0, hs = 0;
    const running = match.map((g) => { ms += g.magnus_score; hs += 1 - g.magnus_score; return [ms, hs]; });
    const labels = match.map((g) => `Game ${g.number}`.replace("Game ", ""));
    const sub = match.map((g, i) => (i % 2 === 0 ? SHORT[g.opening] || g.opening : ""));
    const drawScore = () => lineChart($("chart-score"), {
      labels, sublabels: sub, height: 280,
      series: [{ key: "magnus", values: running.map((r) => r[0]) }, { key: "hans", values: running.map((r) => r[1]) }],
      yMin: 0, yMax: Math.ceil(Math.max(ms, hs)) + 1, yStep: 2, yFmt: (v) => v, endFmt: half,
      tip: (i, key) => gameTip(match[i]) + tipRow(key, `${NAME[key]}: ${half(running[i][key === "magnus" ? 0 : 1])} points so far`),
    });

    // Accuracy per game.
    const drawAccuracy = () => lineChart($("chart-accuracy"), {
      labels, sublabels: sub, height: 300,
      series: [{ key: "magnus", values: mAcc }, { key: "hans", values: hAcc }],
      yMin: 40, yMax: 100, yStep: 10, yFmt: (v) => `${v}%`, endFmt: (v) => `${v.toFixed(1)}%`,
      tip: (i) => gameTip(match[i]) +
        tipRow("magnus", `Magnus: ${pct(mAcc[i])}, ${blunders(match[i], "Magnus")} blunders`) +
        tipRow("hans", `Hans: ${pct(hAcc[i])}, ${blunders(match[i], "Hans")} blunders`),
    });

    // Checkpoints.
    const cp = (n, who) => checkpoints.filter((g) => g.checkpoint === n && g.agent === who);
    const cpAvg = (n, who) => avg(cp(n, who).map((g) => acc(g, who)));
    const cpPoints = (n, who) => cp(n, who).reduce((a, g) => a + g.agent_score, 0);
    const cpTip = (i, key) => {
      const n = cpNumbers[i], who = NAME[key];
      const lines = cp(n, who).map((g) => `As ${g.agent_color}: ${g.agent_score === 1 ? "won" : g.agent_score === 0 ? "lost" : "drew"}, ` +
        `${pct(acc(g, who))}, ${blunders(g, who)} blunders`);
      return `<b>Checkpoint ${n}</b>${tipRow(key, `${who}: ${pct(cpAvg(n, who))} average, ${half(cpPoints(n, who))} of 2 points`)}` +
        `<div class="dim">${lines.join("<br>")}</div>`;
    };
    const drawCheckpoints = () => lineChart($("chart-checkpoints"), {
      labels: cpNumbers.map((n) => `Checkpoint ${n}`),
      sublabels: cpNumbers.map((n) => (n === 0 ? "before game 1" : `after ${n} games`)),
      series: ["magnus", "hans"].map((key) => ({ key, values: cpNumbers.map((n) => cpAvg(n, NAME[key])) })),
      yMin: 40, yMax: 100, yStep: 10, yFmt: (v) => `${v}%`, endFmt: (v) => `${v.toFixed(1)}%`, tip: cpTip, height: 300,
    });

    // Accuracy by opening (the Magnus vs Hans games).
    const openings = [...new Set(match.map((g) => g.opening))];
    const rows = openings.map((name) => {
      const gs = match.filter((g) => g.opening === name);
      return {
        name, label: SHORT[name] || name, highlight: name === "Queen's Gambit Declined",
        magnus: avg(gs.map((g) => acc(g, "Magnus"))), hans: avg(gs.map((g) => acc(g, "Hans"))),
        games: gs.map((g) => ({
          magnus: `Game ${g.number}: ${pct(acc(g, "Magnus"))} (${resultWords(g)})`,
          hans: `Game ${g.number}: ${pct(acc(g, "Hans"))} (${resultWords(g)})`,
        })),
      };
    });
    const drawOpenings = () => dumbbell($("chart-openings"), rows);

    const drawAll = () => { drawScore(); drawAccuracy(); drawCheckpoints(); drawOpenings(); };
    drawAll();
    let timer;
    addEventListener("resize", () => { clearTimeout(timer); timer = setTimeout(drawAll, 120); });

    // Numbers inside the write-up.
    const rulesUsed = match.reduce((a, g) => a + (g.magnus_rules_used || 0), 0);
    const rulesMoves = match.filter((g) => g.notebook_lessons > 0).reduce((a, g) => a + (g.magnus_moves || 0), 0);
    const cpText = (who) => cpNumbers.map((n) => pct(cpAvg(n, who))).join(" → ");
    const fills = {
      score: `${half(magnusPoints)}–${half(hansPoints)}`,
      higher: `${higher} of ${match.length}`,
      v1score: `${half(V1.magnusPoints)}–${half(V1.games - V1.magnusPoints)}, accuracy ${V1.magnusAccuracy}% vs ${V1.hansAccuracy}%`,
      half1: pct(avg(mAcc.slice(0, 6))), half2: pct(avg(mAcc.slice(6))),
      rules: `${Math.round((100 * rulesUsed) / rulesMoves)}%`,
      cpM: cpText("Magnus"), cpH: cpText("Hans"),
      model: `Claude Opus (${data.settings.model_id}), thinking effort "${data.settings.effort}"`,
      requests: games.reduce((a, g) => a + (g.claude_requests || 0), 0).toLocaleString("en"),
    };
    for (const span of document.querySelectorAll("[data-fill]")) span.textContent = fills[span.dataset.fill];

    // Magnus's final notebook: "1. [phase] rule Example: ...".
    const rules = notebookText.split(/\r?\n/).map((l) => l.match(/^\d+\.\s*\[(\w+)\]\s*(.*?)(?:\s+Example:\s*(.*))?$/)).filter(Boolean);
    $("notebook").replaceChildren(...rules.map(([, phase, rule, example]) => {
      const li = document.createElement("li");
      const tag = document.createElement("span");
      tag.className = "phase";
      tag.textContent = phase;
      li.append(tag, rule);
      if (example) {
        const ex = document.createElement("span");
        ex.className = "example";
        ex.textContent = `Example: ${example}`;
        li.append(ex);
      }
      return li;
    }));

    // The table of every game, in the order they were played.
    const order = (g) => (g.kind === "match" ? g.number : g.checkpoint + 0.9);
    const sorted = [...games].sort((a, b) => order(a) - order(b));
    const head = `<tr><th>Game</th><th>Opening</th><th>White</th><th>Black</th><th>Result</th>` +
      `<th class="num">Magnus</th><th class="num">Hans</th><th class="num">Blunders M / H</th><th class="num">Moves</th><th>Watch</th></tr>`;
    let html = head, group = null;
    for (const g of sorted) {
      const grp = g.kind === "match" ? (g.number <= 6 ? "Magnus vs Hans, games 1–6" : "Magnus vs Hans, games 7–12")
        : `Checkpoint ${g.checkpoint} against Stockfish level 0`;
      if (grp !== group) { html += `<tr class="group"><td colspan="10">${grp}</td></tr>`; group = grp; }
      const name = g.kind === "match" ? `Game ${g.number}` : `${g.agent} as ${g.agent_color}`;
      const a = (who) => (acc(g, who) == null ? "" : pct(acc(g, who)));
      const b = (who) => (blunders(g, who) == null ? "–" : blunders(g, who));
      const w = winner(g);
      html += `<tr><td>${name}</td><td>${g.opening || ""}</td>` +
        `<td class="${w === g.white ? "win" : ""}">${g.white}</td><td class="${w === g.black ? "win" : ""}">${g.black}</td>` +
        `<td>${resultWords(g)}</td><td class="num">${a("Magnus")}</td><td class="num">${a("Hans")}</td>` +
        `<td class="num">${b("Magnus")} / ${b("Hans")}</td><td class="num">${g.moves}</td>` +
        `<td><a href="index.html?game=${g.id}">Replay</a> · <a href="live.html?game=${g.id}">3D</a></td></tr>`;
    }
    $("games").innerHTML = html;
  }

  async function start() {
    const [data, notebook] = await Promise.all([
      fetch(`data/results.json?t=${Date.now()}`).then((r) => r.json()),
      fetch("data/magnus-notebook-final.md").then((r) => (r.ok ? r.text() : "")),
    ]);
    render(data, notebook);
  }
  start().catch((err) => { $("tiles").textContent = `Could not load the results: ${err.message}`; });
})();
