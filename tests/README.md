# tests — automatic checks
Small programs that confirm everything still works (illegal moves rejected, diaries replay correctly, and so on).

| Check | What it confirms |
|---|---|
| `check_arbiter.py` | Illegal moves are refused and 20 random games finish and replay correctly. |
| `check_diaries.py` | Every saved diary replays legally, move by move. |
| `check_agent.py` | The Claude player handles answers correctly (uses a pretend Claude, so it costs nothing). |
| `check_website.py` | The replay website works, in a hidden browser (Edge, or Chrome if Edge is missing). |
| `check_stockfish.py` | Move grades are correct and repeatable, and the random player loses to the yardstick. |
| `check_notebook.py` | Magnus's notebook, lesson-writing, merging, colour swaps and resuming (uses a pretend Claude, so it costs nothing). |
| `check_live.py` | The live 3D page: follows a demo game as it is played, and real-speed replays keep both boards correct (no Claude requests). |
