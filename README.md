# Self-Improving AI Chess Agents

**Live replay:** https://johanstanly.github.io/chess-agents/

Two Claude agents play chess against each other. A plain referee program (no AI) checks every move is legal.
Every game is saved as a diary (each move plus what the agent was thinking) and can be replayed on a 2D board in the browser.

Agent A (the learner) writes lessons into a notebook after each loss or draw and reads it before the next game.
Agent B (the control) never learns. The experiment measures whether Agent A's results improve over time.

**Status:** Phase 5 — replay website published on GitHub Pages. Next: the referee and the AI agents.

## Try it
Double-click `serve.bat` to open the replay page in your browser (keep its window open while you use the page).

```
python arena/make_sample_diaries.py   # turn the games in samples/ into diaries
python tests/check_diaries.py         # check every diary move by move
python tests/check_website.py         # check the website in a hidden browser
```

## Credits
- [Stockfish](https://stockfishchess.org/) (GPL-3.0) evaluates positions in the browser.
- [chess.js](https://github.com/jhlywa/chess.js) (BSD-2) checks moves in analysis mode.
- [python-chess](https://github.com/niklasf/python-chess) (GPL-3.0) is the referee's rule book.

## Folders
| Folder | What it is for |
|---|---|
| docs/ | The public replay website (GitHub Pages) |
| arena/ | The referee, players and game runner |
| prompts/ | Instructions given to the agents |
| notebook/ | Agent A's lesson notebook and its history |
| samples/ | Real games used for testing |
| tests/ | Automatic checks |
| tools/ | Helper programs, e.g. the one that draws the pieces |
| engines/ | Local chess engine (not uploaded) |
