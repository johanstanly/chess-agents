# Self-Improving AI Chess Agents

**Live replay:** https://johanstanly.github.io/chess-agents/

Two Claude agents play chess against each other. A plain arbiter program (no AI) checks every move is legal.
Every game is saved as a diary (each move plus what the agent was thinking) and can be replayed on a 2D board in the browser.

Agent A (the learner) writes lessons into a notebook after each loss or draw and reads it before the next game.
Agent B (the control) never learns. The experiment measures whether Agent A's results improve over time.

**Status:** Phase 7 — Claude agents play full games through Claude Code (Pro plan, no paid API). The replay has a thinking card, arrows and captured pieces.

## Try it
Double-click `serve.bat` to open the replay page in your browser (keep its window open while you use the page).

```
python arena/make_sample_diaries.py   # turn the games in samples/ into diaries
python tests/check_diaries.py         # check every diary move by move
python tests/check_website.py         # check the website in a hidden browser
python tests/check_arbiter.py         # check the arbiter: tricky moves, endings, 20 random games
python tests/check_agent.py           # check the Claude agent offline (no AI requests)

python arena/play.py test-moves       # 5 single Claude moves (uses a little Pro allowance)
python arena/play.py game             # one full Claude vs Claude game (about 4% of a 5-hour window)
```

Each Claude move is one short request to Claude Code (`claude -p`) with all tools switched off,
so an agent can only read the position and answer. The agents' instructions are in `prompts/`.

## Credits
- [Stockfish](https://stockfishchess.org/) (GPL-3.0) evaluates positions in the browser.
- [chess.js](https://github.com/jhlywa/chess.js) (BSD-2) checks moves in analysis mode.
- [python-chess](https://github.com/niklasf/python-chess) (GPL-3.0) is the arbiter's rule book (the arbiter is the chess word for referee).

## Folders
| Folder | What it is for |
|---|---|
| docs/ | The public replay website (GitHub Pages) |
| arena/ | The arbiter, players and game runner |
| prompts/ | Instructions given to the agents |
| notebook/ | Agent A's lesson notebook and its history |
| samples/ | Real games used for testing |
| tests/ | Automatic checks |
| tools/ | Helper programs, e.g. the one that draws the pieces |
| engines/ | Local chess engine (not uploaded) |
