"""
Draws our own wood-style chess pieces (inspired by the "Neo-Wood" look,
but our own original drawings) and saves them as 12 SVG files in docs/pieces/.

Each piece is built from simple parts (base, body, collar, head). Every part is
filled with a wood texture, then shaded so it looks rounded, then outlined.

Run:  python tools/make_pieces.py
"""

from pathlib import Path

OUT_DIR = Path(__file__).resolve().parent.parent / "docs" / "pieces"

# Wood colour schemes: base colour, grain streak colour, outline colour.
# "w" is light honey wood, "b" is near-black ebony.
WOODS = {
    "w": {"base": "#e8c48e", "grain": "#b98a52", "outline": "#4a2e14", "seed": 3},
    "b": {"base": "#2b2724", "grain": "#4a4440", "outline": "#050404", "seed": 11},
}

# Shared bases (drawn first, bottom of the piece).
BIG_BASE = ['rect x="17" y="82" width="66" height="11" rx="4.5"',
            'rect x="23" y="75" width="54" height="9" rx="3"']
SMALL_BASE = ['rect x="21" y="82" width="58" height="11" rx="4.5"',
              'rect x="27" y="76" width="46" height="8" rx="3"']

# Each piece: list of parts, drawn in order (later parts sit on top).
# Coordinates are on a 100 x 100 grid.
PIECES = {
    "P": SMALL_BASE + [
        'path d="M33 76 C36 64 42 57 43 50 L57 50 C58 57 64 64 67 76 Z"',
        'rect x="33" y="44" width="34" height="7.5" rx="3.7"',
        'circle cx="50" cy="30" r="14.5"',
    ],
    "R": BIG_BASE + [
        'path d="M29 75 L33 43 L67 43 L71 75 Z"',
        'rect x="27" y="36" width="46" height="8" rx="2"',
        'path d="M26 14 L37 14 L37 21 L45 21 L45 14 L55 14 L55 21 L63 21 L63 14 '
        'L74 14 L74 37 L26 37 Z"',
    ],
    "N": BIG_BASE + [
        'path d="M31 76 C31 64 39 57 45 52 L30 57 Q18 59 16 50 Q15 45 19 41 '
        'L35 24 Q40 17 46 14 L48 5 L55 13 C70 17 79 33 77 52 C76 62 73 69 71 76 Z"',
    ],
    "B": BIG_BASE + [
        'path d="M30 75 C36 64 41 58 41 53 L59 53 C59 58 64 64 70 75 Z"',
        'rect x="32" y="46" width="36" height="7.5" rx="3.7"',
        'path d="M50 13 C66 22 71 35 62 46 L38 46 C29 35 34 22 50 13 Z"',
        'circle cx="50" cy="10" r="5"',
    ],
    "Q": BIG_BASE + [
        'path d="M29 75 C36 63 39 53 38 45 L62 45 C61 53 64 63 71 75 Z"',
        'rect x="30" y="39" width="40" height="7.5" rx="3.7"',
        'path d="M34 40 L28 21 L38 31 L40 15 L46 29 L50 11 L54 29 L60 15 L62 31 '
        'L72 21 L66 40 Z"',
        'circle cx="28" cy="20" r="3.5"', 'circle cx="40" cy="14" r="3.5"',
        'circle cx="50" cy="10" r="3.5"', 'circle cx="60" cy="14" r="3.5"',
        'circle cx="72" cy="20" r="3.5"',
    ],
    "K": BIG_BASE + [
        'path d="M29 75 C36 63 39 53 38 45 L62 45 C61 53 64 63 71 75 Z"',
        'rect x="30" y="39" width="40" height="7.5" rx="3.7"',
        'path d="M34 40 C27 31 32 22 41 24 C44 19 56 19 59 24 C68 22 73 31 66 40 Z"',
        'path d="M47 3 H53 V8 H58 V14 H53 V21 H47 V14 H42 V8 H47 Z"',
    ],
}

# Small details drawn on top in the outline colour.
DETAILS = {
    "N": ['circle cx="37" cy="30" r="2.6" fill="{o}"',
          'circle cx="20.5" cy="48" r="1.6" fill="{o}"',
          'path d="M56 15 C67 21 72 35 71 52" fill="none" stroke="{o}" '
          'stroke-width="2" stroke-linecap="round"'],
    "B": ['path d="M56 22 L47 33" fill="none" stroke="{o}" stroke-width="3" '
          'stroke-linecap="round"'],
}


def piece_svg(color: str, kind: str) -> str:
    w = WOODS[color]
    o = w["outline"]
    parts = []
    for el in PIECES[kind]:
        parts.append(f'<{el} fill="url(#wood)"/>')
        parts.append(f'<{el} fill="url(#shade)" stroke="{o}" stroke-width="2.8" '
                     f'stroke-linejoin="round"/>')
    for el in DETAILS.get(kind, []):
        parts.append(f"<{el.format(o=o)}/>")
    body = "\n  ".join(parts)
    return f'''<svg xmlns="http://www.w3.org/2000/svg" viewBox="-5 -7 110 110">
  <defs>
    <filter id="streaks" x="0" y="0" width="100%" height="100%">
      <feTurbulence type="fractalNoise" baseFrequency="0.22 0.018" numOctaves="3" seed="{w['seed']}" result="n"/>
      <feColorMatrix in="n" type="matrix" values="0 0 0 0 0  0 0 0 0 0  0 0 0 0 0  2.4 0 0 0 -1.05" result="a"/>
      <feFlood flood-color="{w['grain']}" result="c"/>
      <feComposite in="c" in2="a" operator="in"/>
    </filter>
    <pattern id="wood" patternUnits="userSpaceOnUse" width="100" height="100">
      <rect width="100" height="100" fill="{w['base']}"/>
      <rect width="100" height="100" filter="url(#streaks)"/>
    </pattern>
    <linearGradient id="shade" x1="0" y1="0" x2="1" y2="0">
      <stop offset="0" stop-color="#fff" stop-opacity="0.38"/>
      <stop offset="0.35" stop-color="#fff" stop-opacity="0.06"/>
      <stop offset="0.65" stop-color="#000" stop-opacity="0"/>
      <stop offset="1" stop-color="#000" stop-opacity="0.34"/>
    </linearGradient>
  </defs>
  {body}
</svg>
'''


def main() -> None:
    OUT_DIR.mkdir(parents=True, exist_ok=True)
    for color in WOODS:
        for kind in PIECES:
            path = OUT_DIR / f"{color}{kind}.svg"
            path.write_text(piece_svg(color, kind), encoding="utf-8")
            print("saved", path.relative_to(OUT_DIR.parent.parent))


if __name__ == "__main__":
    main()
