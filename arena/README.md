# arena — where games are played
The arbiter, the players (random, Claude, weak engine) and the game runner. Written in Python.

| File | What it does |
|---|---|
| `arbiter.py` | Runs a game, checks every move, saves the diary after each move. |
| `players.py` | Simple players for testing (random moves, scripted moves). |
| `claude_agent.py` | The Claude player (uses your Pro plan via `claude -p`, never the paid API). |
| `stockfish.py` | Stockfish: the yardstick opponent at its weakest (skill 0), and a full-strength copy for grading. |
| `review.py` | Grades every move with Stockfish (Lichess's accuracy formula) and saves the grades in the diary. |
| `play.py` | The commands you run (below). |

Commands:
- `python arena/play.py game`: one Claude vs Claude game.
- `python arena/play.py yardstick`: Claude vs the yardstick (add `--agent-color black` to give Claude Black).
- `python arena/review.py`: grade every game again (free; about 15 seconds per game).
