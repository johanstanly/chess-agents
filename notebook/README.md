# notebook — Magnus's learning material
Magnus (the learner) is sent two things before every move. Claude itself never changes: what changes is the material it reads (memory-based learning).

- `magnus_notebook.md`: at most 15 general rules, each marked opening, middlegame or endgame, with a short example. After every game against Hans (win, draw or loss), Stockfish shows him his 3 worst moves, with the better move and how his move was punished, and he rewrites the whole notebook: keeping, sharpening, merging or replacing rules.
- `mistakes.jsonl`: the mistake library, holding every mistake and blunder he made against Hans. With each move, the 2 from the most similar positions (same phase of the game, most similar pieces on the board) are added to his message.
- `archive.jsonl`: every rule he has ever written, with the game it came from. Nothing is ever deleted from it.
- `history/`: a dated copy of the notebook every time it changed.

Hans (the control) has the same model and the same move protocol minus the notebook step, but never a notebook or a mistake library.
