/*
 * Move sounds, shared by the replay page and the 3D page: a wooden knock for a move,
 * a fuller one for a capture, two knocks for castling, a knock with a small "ding" for
 * check, a chime for promotion and for the end of the game. Made from Kenney's CC0
 * sounds (see sounds/CREDITS.md).
 *
 * Played with the Web Audio API, so a sound starts on the same frame the piece lands.
 * Browsers only allow sound after the visitor's first click or key press on the page;
 * until then sounds are silently skipped. The on/off choice is remembered.
 */
const ChessSound = (() => {
  const NAMES = ["move", "capture", "castle", "check", "promote", "end"];
  const KEY = "chess-sound-off";
  let context = null;
  const buffers = {};
  let off = false;
  try { off = localStorage.getItem(KEY) === "1"; } catch { /* storage blocked: sound stays on */ }
  const listeners = [];

  // The sounds load straight away (an audio context may be created before any click; it
  // just starts paused), so the first move after a click already has its sound.
  const Ctx = window.AudioContext || window.webkitAudioContext;
  if (Ctx) {
    context = new Ctx();
    for (const name of NAMES) {
      fetch(`sounds/${name}.mp3`)
        .then((r) => r.arrayBuffer())
        .then((data) => context.decodeAudioData(data))
        .then((buffer) => { buffers[name] = buffer; })
        .catch(() => { /* a missing sound just stays silent */ });
    }
  }
  // The first click or key press allows sound.
  function unlock() {
    if (context && context.state === "suspended") context.resume();
  }
  for (const type of ["pointerdown", "keydown"]) {
    window.addEventListener(type, unlock, { capture: true, passive: true });
  }

  function play(name) {
    if (off || !context || context.state !== "running" || !buffers[name]) return;
    const source = context.createBufferSource();
    source.buffer = buffers[name];
    source.connect(context.destination);
    source.start();
  }

  /* The right sound for a move, from its written form: "exd5", "O-O", "e8=Q+", "Qh7#"... */
  function forMove(move) {
    const san = (move && move.san) || "";
    if (san.includes("=")) play("promote");
    else if (/[+#]/.test(san)) play("check");
    else if (san.startsWith("O-O")) play("castle");
    else if (san.includes("x")) play("capture");
    else play("move");
  }

  function setOff(value) {
    off = value;
    try { localStorage.setItem(KEY, off ? "1" : "0"); } catch { /* not remembered, still works */ }
    listeners.forEach((fn) => fn(off));
  }

  /* Makes a button switch sound on and off, showing its state. */
  function attachToggle(button) {
    const show = () => {
      button.textContent = off ? "🔇 Sound off" : "🔊 Sound on";
      button.setAttribute("aria-pressed", String(!off));
      button.title = off ? "Turn move sounds on" : "Turn move sounds off";
    };
    button.addEventListener("click", () => setOff(!off));
    listeners.push(show);
    show();
  }

  return { play, forMove, end: () => play("end"), attachToggle };
})();
