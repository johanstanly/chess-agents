# arena — where games are played
The arbiter, the players (random, Claude, weak engine) and the game runner. Written in Python.

| File | What it does |
|---|---|
| `arbiter.py` | Runs a game, checks every move, saves the diary after each move. |
| `players.py` | Simple players for testing (random moves, scripted moves). |
| `claude_agent.py` | The Claude player (uses your Pro plan via `claude -p`, never the paid API). Magnus gets the learner's move protocol, Hans the control's. |
| `stockfish.py` | Stockfish: the yardstick opponent at its weakest (skill 0), and a full-strength copy for grading. |
| `notebook.py` | Magnus's learning material: the notebook (rewritten after every game) and the mistake library (similar past mistakes shown with each move). |
| `openings.py` | The 10 openings the experiment's games start from, and the wrapper that plays them. |
| `puzzles.py` | The puzzle test: 30 positions from version 1's blunders, scored by Stockfish. |
| `experiment.py` | The experiment's schedule, locked settings and results table. |
| `reset_experiment.py` | Archives the old experiment into `experiments/<name>/` and locks the new settings. |
| `live.py` | Keeps `docs/live/status.json` up to date while a game runs, so the live page can follow it; also the free demo players. |
| `review.py` | Grades every move with Stockfish (Lichess's accuracy formula) and saves the grades in the diary. |
| `play.py` | The commands you run (below). |

Commands:
- `python arena/reset_experiment.py`: clean slate. It lists every file it will move into `experiments/v1/` (nothing is deleted), asks you to type YES, then locks the settings (Opus, effort "max") in `experiment.json`.
- `python arena/play.py experiment`: the experiment's next step (`--games 5` plays five). 38 steps in order: checkpoint 0 (a puzzle test for each player, then 4 Stockfish games), Magnus vs Hans games 1–10, checkpoint 10, games 11–20, checkpoint 20. A stopped step continues automatically. Results go to `docs/data/results.json`. While the experiment runs, `game` and `yardstick` are switched off.
- `python arena/play.py test-moves --model opus --effort max`: 5 single moves, to check that a model works (nothing is saved as a game).
- `python arena/play.py game`: one Claude vs Claude test game.
- `python arena/play.py yardstick`: Magnus vs the yardstick (`--agent hans` for Hans, `--agent-color black` for Black).
- `python arena/play.py demo-live`: a free practice game (random moves) to try the live page.
- `python arena/play.py dry-run`: shows exactly what Magnus and Hans are sent, with no Claude requests.
- `python arena/puzzles.py build`: makes the puzzle set from the games in `docs/games` (done once, before version 2).
- `python arena/review.py`: grade every game again (free; about 15 seconds per game).

To watch a game live: double-click `serve.bat`, open http://localhost:8765/live.html, then start a game (e.g. `python arena/play.py experiment`).
