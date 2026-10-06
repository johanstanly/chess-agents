# Self-Improving AI Chess Agents

**Results:** https://johanstanly.github.io/chess-agents/results.html
**Game replays:** https://johanstanly.github.io/chess-agents/ · **3D tavern view:** https://johanstanly.github.io/chess-agents/live.html

Can an AI chess player learn from its own mistakes without being retrained?

Two Claude agents play chess. **Magnus** and **Hans** are the same AI (Claude Opus, thinking effort "high"), with the
same instructions. The only difference is memory:
- After every game, Magnus studies his three worst moves, which the Stockfish chess engine points out along with
  how each one was punished. He then rewrites a notebook of at most 15 rules.
- His mistakes also go into a mistake library. Before every move, he re-reads the notebook and two similar past
  mistakes.
- Hans has no memory: every move, and every game, starts from zero.

A plain arbiter program (no AI) checks that every move is legal. Every game is saved as a diary holding each move,
what the agent was thinking, and Stockfish's grade for the move.

## Results (version 2, October 2026)

| | Magnus (notebook) | Hans (no notebook) |
|---|---|---|
| Score over 12 games against each other | **8½** | 3½ |
| Average accuracy | **81.3%** | 69.4% |
| Games with the higher accuracy | **9** | 3 |
| Accuracy against Stockfish level 0 at checkpoints 0 → 6 → 12 | 86.9 → 82.9 → 89.2% | 88.9 → 71.0 → 64.7% |

**Honest findings:**
- **The notebook gave a clear edge head to head.** In version 1, which used Claude Sonnet at low effort with a
  simpler notebook, the same matchup was even: 4½–5½, with accuracy at 67.8% vs 66.8%.
- **Magnus did not keep improving.** His accuracy was 81.0% in games 1–6 and 81.5% in games 7–12, so the notebook
  acts as a one-off boost. He also outplayed Hans in game 1, before his notebook had any rules, so luck played a
  part.
- **The checkpoints are too noisy to prove anything.** Hans has no memory, so his drop at the checkpoints is pure
  chance, and Magnus's changes are smaller than that swing.
- **The notebook did not transfer to unfamiliar positions.** Its rules were learned from 1.e4 openings. In the
  Queen's Gambit Declined (1.d4), Magnus played no better than Hans.
- **Overall, the result is suggestive, not proven.** With 12 games, a result like this would happen by luck
  roughly 1 time in 10. Proving it would take around 30–40 games.

This is memory-based (in-context) learning: the model itself never changes, only the notes it reads.

## How it works
- Each move is one request to Claude Code (`claude -p`), using a Pro plan and never the paid API. All tools are
  switched off, so an agent can only read the position and answer.
- The agent gets the board, the position code (FEN), the moves so far and the legal moves. It gets no hints about
  attacks or best moves.
- Move protocol, in `prompts/`:
  1. Read the notebook (Magnus only).
  2. Calculate at least two candidate moves and the opponent's best reply to each.
  3. Play the move.
- Settings are fingerprinted and locked before game 1 (`experiment.json`), so nothing can change mid-experiment.
- Results are collected in `docs/data/results.json`. Magnus's notebook is in `notebook/`, with a copy after every
  game in `notebook/history/`. Version 1 is archived in `experiments/v1/`.

## Try it
Double-click `serve.bat` to open the site locally at http://localhost:8765/ (keep its window open).

```
python arena/play.py dry-run          # shows exactly what Magnus and Hans are sent (no AI requests)
python arena/play.py experiment       # plays the next step of the experiment (stops at usage limits; run again to resume)

python tests/check_arbiter.py         # the arbiter: tricky moves, endings, random games
python tests/check_agent.py           # the Claude agent, offline (no AI requests)
python tests/check_notebook.py        # notebook, mistake library, openings, schedule
python tests/check_website.py         # the website in a hidden browser
```

## Credits
- [Claude](https://www.anthropic.com/claude) (Anthropic) plays the games.
- [Stockfish](https://stockfishchess.org/) (GPL-3.0) is the opponent at the checkpoints, grades every move, and
  evaluates positions in the browser.
- [python-chess](https://github.com/niklasf/python-chess) (GPL-3.0) is the arbiter's rule book.
- [chess.js](https://github.com/jhlywa/chess.js) (BSD-2) checks moves in the replay's analysis mode.
- [Three.js](https://threejs.org/) (MIT) and the CC0 [KayKit](https://kaylousberg.com/) and
  [Kenney](https://kenney.nl/) asset packs make the 3D tavern.

## Folders
| Folder | What it is for |
|---|---|
| docs/ | The public website (GitHub Pages): replays, 3D view, results |
| arena/ | The arbiter, the agents, the experiment runner |
| prompts/ | Instructions given to the agents |
| notebook/ | Magnus's notebook, its history and his mistake library |
| experiments/ | Archived earlier versions of the experiment |
| samples/ | Real games used for testing |
| tests/ | Automatic checks |
| tools/ | Helper programs, e.g. the one that draws the pieces |
| engines/ | Local chess engine (not uploaded) |
