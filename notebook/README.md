# notebook — Magnus's lessons
Magnus (the learner) reads `magnus_notebook.md` before every move. After each game against Hans that he does not win, Stockfish shows him his 3 worst moves (with the better move), and he writes up to 3 general lessons.

- `magnus_notebook.md`: the lessons he reads during games (at most 15; when it overflows he merges them down to 10).
- `archive.jsonl`: every lesson he has ever written, with the game it came from. Nothing is ever deleted from it.
- `history/`: a dated copy of the notebook every time it changed.

Hans (the control) has the same instructions and model, but never a notebook.
This is memory-based learning: Claude itself is never retrained; what changes is the notebook it reads.
