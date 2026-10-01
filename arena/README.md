# arena — where games are played
The arbiter, the players (random, Claude, weak engine) and the game runner. Written in Python.

| File | What it does |
|---|---|
| `arbiter.py` | Runs a game, checks every move, saves the diary after each move. |
| `players.py` | Simple players for testing (random moves, scripted moves). |
| `claude_agent.py` | The Claude player (uses your Pro plan via `claude -p`, never the paid API). |
| `stockfish.py` | Stockfish: the yardstick opponent at its weakest (skill 0), and a full-strength copy for grading. |
| `notebook.py` | Magnus's notebook: lesson-writing after games he does not win, merging, archive and dated copies. |
| `live.py` | Keeps `docs/live/status.json` up to date while a game runs, so the live page can follow it; also the free demo players. |
| `review.py` | Grades every move with Stockfish (Lichess's accuracy formula) and saves the grades in the diary. |
| `play.py` | The commands you run (below). |

Commands:
- `python arena/play.py game`: one Claude vs Claude game.
- `python arena/reset_experiment.py`: clean slate for the experiment. It lists what it will delete, asks you to type YES, then locks the settings in `experiment.json`.
- `python arena/play.py experiment`: the experiment's next game (`--games 5` plays five). That is 32 games in order: Stockfish checkpoint 0 (4 games), Magnus vs Hans games 1–10, checkpoint 10, games 11–20, checkpoint 20. A stopped game continues automatically. Results go to `docs/data/results.json`. While the experiment runs, `game` and `yardstick` are switched off.
- `python arena/play.py yardstick`: Magnus vs the yardstick (`--agent hans` for Hans, `--agent-color black` for Black). No lessons are written.
- `python arena/play.py demo-live`: a free practice game (random moves) to try the live page.
- `python arena/play.py dry-run`: shows exactly what Magnus and Hans are sent, with no Claude requests.
- `python arena/review.py`: grade every game again (free; about 15 seconds per game).

To watch a game live: double-click `serve.bat`, open http://localhost:8000/live.html, then start a game (e.g. `python arena/play.py experiment`).
