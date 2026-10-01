/*
 * The 3D room: Magnus and Hans sit at a small table in a cosy tavern and play.
 * Built with Three.js (a free 3D library). Models: KayKit by Kay Lousberg (CC0),
 * see models/CREDITS.md. The idea comes from Bot Crossing by Jarren Rocks.
 *
 * What the live page can ask the room to do:
 *   room.think(color)          the player starts thinking ("…" bubble)
 *   room.say(color, text)      show (and type out) that player's thought
 *   room.moved(color, move)    the player picks up the piece and plays it (resolves when it lands)
 *   room.setPosition(fen)      the little chess set on the table shows this position
 *   room.finish(result)        "1-0", "0-1" or "1/2-1/2": winner cheers, loser slumps
 */

import * as THREE from "three";
import { GLTFLoader } from "three/addons/loaders/GLTFLoader.js";
import { OrbitControls } from "three/addons/controls/OrbitControls.js";
import { CSS2DObject, CSS2DRenderer } from "three/addons/renderers/CSS2DRenderer.js";
import { clone as cloneCharacter } from "three/addons/utils/SkeletonUtils.js";

const MODELS = "models/";
const TABLE_HEIGHT = 1.0;         // the table is 1 unit high
const CANDLE_Z = -0.72;           // the candle stands at the back end of the table, clear of the board
const SEAT_DISTANCE = 0.82;       // how far each player is from the table's centre (close enough to reach)
const HIPS_BEHIND = 0.40;         // the sitting animation puts the hips this far behind the player's spot
const TYPE_SPEED = 40;            // letters per second when a thought is typed out (as in liveview.js)
const LEAN = 0.35;                // how far a player leans toward the piece (0 = not at all, 1 = fully)
const MOVE_SECONDS = 1.2;         // reach, pick up, carry, put down, pull back (at 1x speed)
const LINGER_SECONDS = 0.6;       // the last thought fades soon after the other player starts (it was already read)
const LABEL_HEIGHT = 1.45;        // name tag height above the head bone (clears hats and helmets)

const ROOM_HALF = 10;             // the room runs from -10 to +10 in both directions

// Things each character holds that we hide (they are here to play chess, not fight).
const HIDDEN_PARTS = /Wand|Staff|Spellbook|Sword|Shield|Crossbow|Knife|Throwable|Axe|Mug/i;

/* Who looks like whom. Magnus and Hans are the two AI agents; the famous players
   of the sample games each get a character of their own. Anyone else (older
   test games, Stockfish) borrows the wizard as White or the knight as Black. */
const CAST = {
  "Magnus": { model: "Mage", role: "learner" },
  "Hans": { model: "Knight", role: "control", helmet: false },   // no helmet: we want to see his face
  "Garry Kasparov": { model: "Barbarian" },
  "Veselin Topalov": { model: "Rogue" },
  "Edward Lasker": { model: "Rogue_Hooded" },
  "George Alan Thomas": { model: "Knight", helmet: true, cape: 0x2f7a4a },   // green cape: not Hans
};
const STAND_INS = { white: { model: "Mage" }, black: { model: "Knight", helmet: false } };

export class ChessRoom {
  constructor(container) {
    this.container = container;
    this.clock = new THREE.Clock();
    this.players = {};            // "white" / "black" -> Character
    this.swaying = true;          // the camera drifts slowly until you move it yourself
    this.speed = 1;               // replay speed: thoughts are typed faster at 2x, 4x...

    this.renderer = new THREE.WebGLRenderer({ antialias: true });
    this.renderer.setPixelRatio(Math.min(window.devicePixelRatio, 2));
    this.renderer.shadowMap.enabled = true;
    this.renderer.shadowMap.type = THREE.PCFSoftShadowMap;
    this.renderer.toneMapping = THREE.ACESFilmicToneMapping;
    this.renderer.toneMappingExposure = 1.05;
    container.appendChild(this.renderer.domElement);

    // A second, invisible layer for the name tags and thought bubbles (normal web text).
    this.labels = new CSS2DRenderer();
    this.labels.domElement.className = "room-labels";
    container.appendChild(this.labels.domElement);

    this.scene = new THREE.Scene();
    this.scene.background = new THREE.Color(0x1d1712);
    this.scene.fog = new THREE.Fog(0x1d1712, 14, 30);

    this.camera = new THREE.PerspectiveCamera(38, 1, 0.1, 100);
    this.camera.position.set(0, 3.9, 7.6);     // straight in front: both players seen from the side
    this.controls = new OrbitControls(this.camera, this.labels.domElement);
    this.controls.target.set(0, 1.4, 0);
    this.controls.enableDamping = true;
    this.controls.enablePan = false;
    this.controls.minDistance = 3;
    this.controls.maxDistance = ROOM_HALF - 1.5;   // turn all the way round, but stay inside the room
    this.controls.minPolarAngle = 0.35;
    this.controls.maxPolarAngle = 1.35;       // never below the floor
    this.controls.addEventListener("start", () => { this.swaying = false; });
    this.baseAngle = Math.atan2(this.camera.position.x, this.camera.position.z);

    this.addLights();
    new ResizeObserver(() => this.resize()).observe(container);
    this.resize();
    this.renderer.setAnimationLoop(() => this.frame());
  }

  /* Loads the room; resolves when it is ready. The players are added by setPlayers(). */
  async load() {
    const loader = new GLTFLoader();
    const cache = {};
    const get = (name) => (cache[name] ||= loader.loadAsync(`${MODELS}${name}.glb`));
    this.getModel = get;
    const place = async (name, x, y, z, turn = 0, scale = 1) => {
      const model = (await get(name)).scene.clone();
      model.position.set(x, y, z);
      model.rotation.y = turn;
      model.scale.setScalar(scale);
      model.traverse((o) => { if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; } });
      this.scene.add(model);
      return model;
    };

    const jobs = [];
    const H = ROOM_HALF, spots = [-8, -4, 0, 4, 8];
    // Floor: 5 x 5 wooden tiles (each 4 x 4 units).
    for (const x of spots) for (const z of spots) jobs.push(place("floor_wood_large", x, 0, z));
    // Four walls, each turned to face into the room, with windows in the back and front.
    for (const s of spots) {
      jobs.push(place(s === 0 ? "wall_window_open" : "wall", s, 0, -H));
      jobs.push(place(s === 0 ? "wall_window_open" : "wall", s, 0, H, Math.PI));
      jobs.push(place("wall", -H, 0, s, Math.PI / 2), place("wall", H, 0, s, -Math.PI / 2));
    }
    // Torches (with fire) on every wall: x, z, turn so they face the room.
    this.flames = [];
    const torches = [[-4, -H + 0.5, 0], [4, -H + 0.5, 0], [-H + 0.5, -2, Math.PI / 2], [-H + 0.5, 4, Math.PI / 2],
                     [H - 0.5, -2, -Math.PI / 2], [H - 0.5, 4, -Math.PI / 2], [-4, H - 0.5, Math.PI], [4, H - 0.5, Math.PI]];
    for (const [x, z, turn] of torches) {
      jobs.push(place("torch_mounted", x, 2.2, z, turn).then((torch) => {
        const flame = new Flame();
        flame.group.position.set(0, 0.66, 0.4);   // in the torch's cup
        torch.add(flame.group);
        this.flames.push(flame);
      }));
    }
    // Furniture and decoration along the walls.
    jobs.push(place("shelves", -6.5, 0, -H - 0.2), place("shelves", 6.5, 0, -H - 0.2),
              place("shelf_small_candles", 0, 2.6, -H + 0.5));
    jobs.push(place("banner_patternA_red", -H - 0.2, 0.2, -6, Math.PI / 2), place("banner_patternA_blue", -H - 0.2, 0.2, 1, Math.PI / 2),
              place("banner_patternA_blue", H + 0.2, 0.2, -6, -Math.PI / 2), place("banner_patternA_red", H + 0.2, 0.2, 1, -Math.PI / 2));
    jobs.push(place("barrel_large", -8.6, 0, -8.6), place("barrel_large", 8.6, 0, 8.4, 0.4),
              place("keg", -8.4, 0, 7.8, 0.6), place("bottle_A_green", -8.4, 2.05, 7.8),
              place("shelves", -2.5, 0, H + 0.2, Math.PI), place("shelves", 2.5, 0, H + 0.2, Math.PI));
    // The table, its candle and the two chairs.
    // A long table turned sideways and made smaller (1.1 wide, 2 long): the players sit
    // across its narrow side, close enough to reach every square.
    jobs.push(place("table_long", 0, 0, 0).then((table) => table.scale.set(0.55, 1, 0.5)));
    jobs.push(place("candle_lit", 0, TABLE_HEIGHT, CANDLE_Z, 0, 0.6));
    // Stools rather than chairs: a backrest would poke through the players' capes.
    const seat = SEAT_DISTANCE + HIPS_BEHIND;   // right under the hips
    jobs.push(place("stool", -seat, 0, 0), place("stool", seat, 0, 0));

    this.chessSet = new ChessSet();
    this.chessSet.group.position.set(0, TABLE_HEIGHT + 0.005, 0);
    this.scene.add(this.chessSet.group);
    await Promise.all(jobs);
    await this.setPlayers("Magnus", "Hans");
  }

  /* Seats the two players of a game: White on the left (seen from the camera),
     Black on the right. Each player's character is loaded the first time it is needed. */
  async setPlayers(whiteName, blackName) {
    const key = `${whiteName}|${blackName}`;
    if (this.seated === key || this.wanted === key) return;
    this.wanted = key;   // "seated" is set once they are really in their chairs
    const make = async (name, color) => {
      const look = CAST[name] || STAND_INS[color];
      const gltf = await this.getModel(look.model);
      return new Character(gltf, name, look, this);
    };
    const [white, black] = await Promise.all([make(whiteName, "white"), make(blackName, "black")]);
    if (this.wanted !== key) { white.remove(); black.remove(); return; }   // another game was chosen meanwhile
    this.cancelMove();
    for (const p of Object.values(this.players)) p.remove();
    white.seat(-SEAT_DISTANCE, Math.PI / 2);
    black.seat(SEAT_DISTANCE, -Math.PI / 2);
    this.players = { white, black };
    this.characters = { [whiteName]: white, [blackName]: black };
    this.seated = key;
    this.wanted = null;
    this.chessSet.orient();   // White's side of the little board faces the White player
  }

  addLights() {
    this.scene.add(new THREE.HemisphereLight(0xffe2b8, 0x2a1d14, 0.9));
    const sun = new THREE.DirectionalLight(0xfff0d8, 1.4);   // daylight through the window
    sun.position.set(2, 9, -8);
    sun.castShadow = true;
    sun.shadow.mapSize.set(2048, 2048);
    Object.assign(sun.shadow.camera, { left: -7, right: 7, top: 7, bottom: -7 });
    this.scene.add(sun);
    this.candle = new THREE.PointLight(0xffa64d, 6, 6, 1.6);   // the candle on the table flickers
    this.candle.position.set(0, TABLE_HEIGHT + 0.8, CANDLE_Z);
    this.scene.add(this.candle);
  }

  resize() {
    const { clientWidth: w, clientHeight: h } = this.container;
    if (!w || !h) return;
    this.renderer.setSize(w, h);
    this.labels.setSize(w, h);
    this.camera.aspect = w / h;
    this.camera.updateProjectionMatrix();
  }

  frame() {
    const dt = Math.min(this.clock.getDelta(), 0.1);
    const t = this.clock.elapsedTime;
    if (this.swaying) {   // a slow drift from side to side
      const angle = this.baseAngle + 0.16 * Math.sin(t / 14);
      const r = Math.hypot(this.camera.position.x, this.camera.position.z);
      this.camera.position.x = r * Math.sin(angle);
      this.camera.position.z = r * Math.cos(angle);
    }
    this.candle.intensity = 6 + Math.sin(t * 9) * 0.5 + Math.sin(t * 23) * 0.3;
    for (const f of this.flames || []) f.update(t);
    this.updateMove(t);
    for (const c of Object.values(this.characters || {})) c.update(dt, t);
    this.controls.update();
    this.renderer.render(this.scene, this.camera);
    this.labels.render(this.scene, this.camera);
    const box = this.container.getBoundingClientRect();
    for (const c of Object.values(this.players)) c.keepInView(box);
  }

  // ---------- What the live page uses ----------
  think(color) {
    // Only the player whose turn it is has a bubble; the other one's fades away.
    for (const [c, p] of Object.entries(this.players)) if (c !== color) p.quiet();
    this.players[color]?.think();
  }
  say(color, text, instant = false) { this.players[color]?.say(text, instant); }
  whenTyped(color) { return this.players[color]?.whenTyped() ?? Promise.resolve(); }

  /* The player reaches for the piece, carries it to its new square and pulls back.
     Returns a promise that resolves when the piece is put down. Without `move`
     (e.g. when jumping through a game) the piece is simply placed. */
  moved(color, move = null) {
    const player = this.players[color];
    this.cancelMove();
    player?.madeMove();
    const piece = move && this.chessSet.bySquare[move.from];
    if (!player || !piece) {
      if (move) this.chessSet.setPosition(move.fen_after);
      return Promise.resolve();
    }
    const from = this.chessSet.local(move.from), to = this.chessSet.local(move.to);
    player.chooseArm(this.chessSet.group.localToWorld(from.clone()));
    return new Promise((resolve) => {
      this.move = { move, player, piece, from, to, resolve, landed: false,
                    start: this.clock.elapsedTime, duration: MOVE_SECONDS / this.speed };
    });
  }

  updateMove(t) {
    const mv = this.move;
    if (!mv) return;
    const k = (t - mv.start) / mv.duration;                 // 0 -> 1 over the whole move
    const smooth = (x) => { x = Math.min(1, Math.max(0, x)); return x * x * (3 - 2 * x); };
    const carried = smooth((k - 0.3) / 0.45);               // the piece travels from 30% to 75%
    if (!mv.landed && k >= 0.3) {
      mv.piece.position.lerpVectors(mv.from, mv.to, carried);
      mv.piece.position.y = mv.from.y + Math.sin(Math.PI * carried) * 0.09;   // a little hop
    }
    const hand = (k < 0.3 ? mv.from : k < 0.75 ? mv.piece.position : mv.to).clone();
    hand.y += 0.07;                                          // fingers just above the piece
    const weight = k < 0.25 ? smooth(k / 0.25) : k < 0.8 ? 1 : smooth(1 - (k - 0.8) / 0.2);
    mv.player.reachTo(this.chessSet.group.localToWorld(hand), weight);
    if (!mv.landed && k >= 0.75) {
      mv.landed = true;
      this.chessSet.setPosition(mv.move.fen_after);         // captures, castling, promotion
      mv.resolve();
    }
    if (k >= 1) { mv.player.reachTo(null, 0); this.move = null; }
  }

  cancelMove() {
    if (!this.move) return;
    this.move.player.reachTo(null, 0);
    this.move = null;   // its promise never resolves: whoever waited has moved on
  }

  setPosition(fen) { this.cancelMove(); this.chessSet?.setPosition(fen); }
  finish(result) {
    const outcome = { "1-0": ["win", "loss"], "0-1": ["loss", "win"] }[result] || ["draw", "draw"];
    this.players.white?.finish(outcome[0]);
    this.players.black?.finish(outcome[1]);
  }
  reset() { this.cancelMove(); for (const p of Object.values(this.players)) p.reset(); }
}

/* One animated character with a name tag, a status badge and a thought bubble. */
class Character {
  constructor(gltf, name, look, room) {
    this.name = name;
    this.room = room;
    this.model = cloneCharacter(gltf.scene);   // its own copy, so two players can share a model file
    this.model.traverse((o) => {
      if (o.isMesh) { o.castShadow = true; o.receiveShadow = true; }
      if (HIDDEN_PARTS.test(o.name)) o.visible = false;
      if (/Helmet/.test(o.name) && look.helmet === false) o.visible = false;
      if (/Cape/.test(o.name) && look.cape && o.material) {
        o.material = o.material.clone();
        o.material.color.setHex(look.cape);
      }
    });
    const role = look.role || "guest";
    room.scene.add(this.model);
    this.mixer = new THREE.AnimationMixer(this.model);
    this.clips = Object.fromEntries(gltf.animations.map((a) => [a.name, a]));
    this.head = this.model.getObjectByName("head");
    this.arms = {};
    for (const side of ["l", "r"]) {
      // Three.js drops the dots from names when loading: "upperarm.r" becomes "upperarmr".
      this.arms[side] = ["upperarm", "lowerarm", "hand"].map((b) => this.model.getObjectByName(`${b}${side}`));
    }
    this.arm = this.arms.r;
    this.spine = this.model.getObjectByName("spine");
    this.chest = this.model.getObjectByName("chest");
    this.reachPoint = null;       // where the hand is heading (a point in the room), or null
    this.reachWeight = 0;         // 0 = the arm follows the sitting animation, 1 = fully reaching
    this.typed = "";              // the part of the thought already typed into the bubble
    this.target = "";             // the whole thought being typed

    // The label floating above the head (web text, so it stays sharp).
    this.label = document.createElement("div");
    this.label.className = `agent-label ${role}`;
    this.label.innerHTML = `<div class="thought-cloud" hidden></div><div class="badge" hidden></div>` +
                           `<div class="nametag"></div>`;
    this.label.querySelector(".nametag").textContent = name;
    this.bubble = this.label.querySelector(".thought-cloud");
    this.badge = this.label.querySelector(".badge");
    this.anchor = new CSS2DObject(this.label);
    this.anchor.center.set(0.5, 1);   // the label's bottom middle sits on the anchor point
    room.scene.add(this.anchor);
    this.play("Sit_Chair_Idle");
  }

  /* Takes the character (and its label) out of the room. */
  remove() {
    this.stopTyping();
    clearTimeout(this.fadeTimer);
    this.room.scene.remove(this.model, this.anchor);
  }

  seat(x, turn) {
    this.model.position.set(x, 0, 0);
    this.model.rotation.y = turn;
  }

  play(name, { once = false, fade = 0.35 } = {}) {
    const clip = this.clips[name];
    if (!clip) return;
    const action = this.mixer.clipAction(clip);
    action.reset();
    action.setLoop(once ? THREE.LoopOnce : THREE.LoopRepeat);
    action.clampWhenFinished = once;
    if (this.current && this.current !== action) this.current.crossFadeTo(action, fade, false);
    action.play();
    this.current = action;
  }

  setBadge(text) {
    this.badge.hidden = !text;
    this.badge.textContent = text || "";
  }

  /* The other player's turn: the badge goes, and the bubble fades after a moment for reading. */
  quiet() {
    if (this.state === "finished") return;
    this.state = "idle";
    this.setBadge(null);
    clearTimeout(this.fadeTimer);
    this.fadeTimer = setTimeout(() => {
      if (this.state !== "idle") return;
      this.stopTyping();
      this.bubble.classList.add("gone");
      this.fadeTimer = setTimeout(() => { if (this.state === "idle") this.bubble.hidden = true; }, 450);
    }, LINGER_SECONDS * 1000 / this.room.speed);
  }

  think() {
    this.state = "thinking";
    this.setBadge("…");
    clearTimeout(this.fadeTimer);
    this.bubble.classList.remove("gone");
    this.stopTyping();
    this.bubble.hidden = false;
    this.bubble.classList.add("thinking");
    this.bubble.innerHTML = "<span></span><span></span><span></span>";
  }

  /* Types the thought out at a readable pace (Claude writes far faster than we can read). */
  say(text, instant = false) {
    if (!text) return;
    this.bubble.hidden = false;
    this.bubble.classList.remove("thinking", "gone");
    if (instant) { this.stopTyping(); this.bubble.textContent = text; this.typed = text; return; }
    if (this.target === text) return;
    this.target = text;
    if (!text.startsWith(this.typed)) this.typed = "";
    this.stopTyping();
    // Letters appear by elapsed time, not one per tick: browsers slow fast timers
    // down (e.g. in background tabs), which would otherwise make typing crawl.
    const startedAt = performance.now(), from = this.typed.length;
    this.typer = setInterval(() => {
      const elapsed = (performance.now() - startedAt) / 1000;
      const count = Math.min(this.target.length, from + Math.floor(elapsed * TYPE_SPEED * this.room.speed));
      this.typed = this.target.slice(0, count);
      this.bubble.textContent = this.typed;
      if (count >= this.target.length) this.stopTyping();
    }, 40);
  }

  stopTyping() { clearInterval(this.typer); this.typer = null; }

  /* Resolves once the whole thought is in the bubble. */
  whenTyped() {
    return new Promise((resolve) => {
      const check = () => (this.typer ? setTimeout(check, 100) : resolve());
      check();
    });
  }

  madeMove() {
    this.state = "moved";
    this.setBadge("♟");
    // No thought was shared (e.g. famous sample games): the "…" bubble goes away.
    if (this.bubble.classList.contains("thinking")) this.bubble.hidden = true;
  }

  /* Uses the arm on the same side as the piece. */
  chooseArm(point) {
    const right = new THREE.Vector3(-1, 0, 0).applyQuaternion(this.model.quaternion);
    const side = point.clone().sub(this.model.position).dot(right) >= 0 ? "r" : "l";
    this.arm = this.arms[side].every(Boolean) ? this.arms[side] : this.arms.r;
  }

  reachTo(point, weight) {
    this.reachPoint = point;
    this.reachWeight = point ? weight : 0;
  }

  /* Turns a bone so that the next bone along the arm points at `target` (blended by weight). */
  static aim(bone, child, target, weight) {
    const along = child.position.clone().normalize();                 // the bone's own direction
    const now = along.applyQuaternion(bone.quaternion);                // ...in its parent's space
    const parentTurn = bone.parent.getWorldQuaternion(new THREE.Quaternion()).invert();
    const want = target.clone().sub(bone.getWorldPosition(new THREE.Vector3()))
      .normalize().applyQuaternion(parentTurn);
    const aimed = new THREE.Quaternion().setFromUnitVectors(now, want).multiply(bone.quaternion);
    bone.quaternion.slerp(aimed, weight);
    bone.updateMatrixWorld(true);
  }

  finish(outcome) {
    this.state = "finished";
    this.stopTyping();
    this.setBadge({ win: "✓", loss: "✗", draw: "½" }[outcome]);
    if (outcome === "win") {
      this.play("Sit_Chair_StandUp", { once: true });
      setTimeout(() => this.play("Cheer"), 1400);
    }
    this.slump = outcome === "loss";
  }

  reset() {
    this.stopTyping();
    clearTimeout(this.fadeTimer);
    this.reachTo(null, 0);
    this.slump = false;
    this.state = "idle";
    this.typed = this.target = "";
    this.bubble.hidden = true;
    this.setBadge(null);
    this.play("Sit_Chair_Idle");
  }

  update(dt, t) {
    this.mixer.update(dt);
    // Small touches on top of the sitting animation: reaching for a piece, thinking, slumping.
    const [upper, lower, hand] = this.arm;
    if (this.reachPoint && this.reachWeight > 0.001 && upper && lower && hand) {
      this.model.updateMatrixWorld(true);
      if (this.spine && this.chest) Character.aim(this.spine, this.chest, this.reachPoint, this.reachWeight * LEAN);
      Character.aim(upper, lower, this.reachPoint, this.reachWeight);
      Character.aim(lower, hand, this.reachPoint, this.reachWeight);
    }
    if (this.head) {
      if (this.state === "thinking") this.head.rotation.z += Math.sin(t * 1.3) * 0.12;   // a thoughtful tilt
      if (this.slump) this.head.rotation.x += 0.45;
    }
    // Keep the label just above the head.
    if (this.head) {
      this.head.getWorldPosition(this.anchor.position);
      this.anchor.position.y += LABEL_HEIGHT;
    }
  }

  /* Slides the thought bubble back inside the 3D window if it would stick out of it
     (on a narrow phone screen the players sit close to the edges). The little tail
     moves the other way, so it still points at the player. */
  keepInView(box) {
    if (this.bubble.hidden) return;
    const label = this.label.getBoundingClientRect();   // not moved by the bubble's own shift
    const half = this.bubble.offsetWidth / 2, centre = label.left + label.width / 2, gap = 6;
    let dx = 0;
    if (centre - half < box.left + gap) dx = box.left + gap - (centre - half);
    else if (centre + half > box.right - gap) dx = box.right - gap - (centre + half);
    const dy = Math.max(0, box.top + gap - label.top);
    const tail = Math.max(-(half - 14), Math.min(half - 14, -dx));
    this.bubble.style.transform = dx || dy ? `translate(${dx}px, ${dy}px)` : "";
    this.bubble.style.setProperty("--tail", `${tail}px`);
  }
}

/* The little chess set on the table: our own simple wooden pieces. */
class ChessSet {
  constructor() {
    this.group = new THREE.Group();
    const size = 0.78, square = size / 8;
    this.square = square;
    const light = new THREE.MeshStandardMaterial({ color: 0xe9dcc2, roughness: 0.6 });
    const dark = new THREE.MeshStandardMaterial({ color: 0x55605a, roughness: 0.6 });
    const frame = new THREE.Mesh(new THREE.BoxGeometry(size + 0.06, 0.03, size + 0.06),
                                 new THREE.MeshStandardMaterial({ color: 0x6b4128, roughness: 0.7 }));
    frame.position.y = 0.015;
    frame.receiveShadow = true;
    this.group.add(frame);
    const tile = new THREE.BoxGeometry(square, 0.01, square);
    for (let f = 0; f < 8; f++) for (let r = 0; r < 8; r++) {
      const m = new THREE.Mesh(tile, (f + r) % 2 ? light : dark);
      m.position.set((f - 3.5) * square, 0.035, (3.5 - r) * square);
      m.receiveShadow = true;
      this.group.add(m);
    }
    this.pieces = new THREE.Group();
    this.group.add(this.pieces);
    this.materials = {
      w: new THREE.MeshStandardMaterial({ color: 0xe8c48c, roughness: 0.5 }),
      b: new THREE.MeshStandardMaterial({ color: 0x2a211c, roughness: 0.5 }),
    };
    this.setPosition("rnbqkbnr/pppppppp/8/8/8/8/PPPPPPPP/RNBQKBNR w KQkq - 0 1");
  }

  /* White sits on the left (negative x), so files run along z and ranks along x. */
  orient() { this.group.rotation.y = -Math.PI / 2; }

  /* Where a square is, in the chess set's own coordinates. */
  local(square) {
    const file = square.charCodeAt(0) - 97, rank = Number(square[1]) - 1;
    return new THREE.Vector3((file - 3.5) * this.square, 0.04, (3.5 - rank) * this.square);
  }

  setPosition(fen) {
    if (fen === this.fen) return;
    this.fen = fen;
    this.pieces.clear();
    this.bySquare = {};
    const rows = fen.split(" ")[0].split("/");
    rows.forEach((row, i) => {
      let file = 0;
      for (const ch of row) {
        if (/\d/.test(ch)) { file += Number(ch); continue; }
        const piece = makePiece(ch.toLowerCase(), this.materials[ch === ch.toUpperCase() ? "w" : "b"]);
        piece.position.set((file - 3.5) * this.square, 0.04, (i - 3.5) * this.square);
        this.pieces.add(piece);
        this.bySquare[String.fromCharCode(97 + file) + (8 - i)] = piece;
        file += 1;
      }
    });
  }
}

/* A tiny chess piece made of simple shapes: taller for more important pieces. */
function makePiece(type, material) {
  const heights = { p: 0.05, n: 0.07, b: 0.075, r: 0.065, q: 0.085, k: 0.095 };
  const h = heights[type];
  const group = new THREE.Group();
  const body = new THREE.Mesh(new THREE.CylinderGeometry(0.014, 0.024, h, 12), material);
  body.position.y = h / 2;
  const top = new THREE.Mesh(type === "r" ? new THREE.CylinderGeometry(0.02, 0.02, 0.02, 12)
                                          : new THREE.SphereGeometry(type === "p" ? 0.017 : 0.019, 12, 8), material);
  top.position.y = h + 0.008;
  for (const m of [body, top]) { m.castShadow = true; group.add(m); }
  return group;
}

/* A burning torch flame: two glowing cones and a soft halo that flicker, plus the
   light the fire casts on the walls. */
class Flame {
  constructor() {
    this.group = new THREE.Group();
    this.seed = Math.random() * 100;
    const glow = (color, opacity) => new THREE.MeshBasicMaterial({
      color, transparent: true, opacity, depthWrite: false, blending: THREE.AdditiveBlending });
    this.outer = new THREE.Mesh(new THREE.ConeGeometry(0.13, 0.42, 10), glow(0xff6a1a, 0.9));
    this.inner = new THREE.Mesh(new THREE.ConeGeometry(0.07, 0.26, 10), glow(0xffd36b, 0.95));
    this.outer.position.y = 0.2;
    this.inner.position.y = 0.13;
    this.halo = new THREE.Sprite(new THREE.SpriteMaterial({
      map: haloTexture(), color: 0xff9a40, transparent: true, opacity: 0.55,
      depthWrite: false, blending: THREE.AdditiveBlending }));
    this.halo.scale.setScalar(0.9);
    this.halo.position.y = 0.2;
    this.light = new THREE.PointLight(0xff8a3d, 7, 7, 1.6);
    this.light.position.y = 0.3;
    this.group.add(this.outer, this.inner, this.halo, this.light);
  }

  update(t) {
    const s = t * 11 + this.seed;
    const flicker = 1 + Math.sin(s) * 0.08 + Math.sin(s * 2.3) * 0.06 + Math.sin(s * 5.1) * 0.04;
    this.outer.scale.set(1 + Math.sin(s * 1.7) * 0.06, flicker, 1 + Math.cos(s * 1.3) * 0.06);
    this.inner.scale.set(1, 1 + Math.sin(s * 3.1) * 0.1, 1);
    this.outer.rotation.y = s * 0.3;
    this.outer.rotation.z = Math.sin(s * 0.9) * 0.08;   // the flame sways a little
    this.halo.material.opacity = 0.45 + (flicker - 1) * 1.2;
    this.light.intensity = 7 * flicker;
  }
}

/* A soft round glow, drawn once and shared by every flame. */
let haloCache = null;
function haloTexture() {
  if (haloCache) return haloCache;
  const c = document.createElement("canvas");
  c.width = c.height = 64;
  const g = c.getContext("2d");
  const grad = g.createRadialGradient(32, 32, 0, 32, 32, 32);
  grad.addColorStop(0, "rgba(255,255,255,1)");
  grad.addColorStop(0.35, "rgba(255,255,255,0.45)");
  grad.addColorStop(1, "rgba(255,255,255,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, 64, 64);
  haloCache = new THREE.CanvasTexture(c);
  return haloCache;
}
