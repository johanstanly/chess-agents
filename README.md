# Self-Improving AI Chess Agents

Two Claude agents play chess against each other. A plain referee program (no AI) checks every move is legal.
Every game is saved as a diary (each move plus what the agent was thinking) and can be replayed on a 2D board in the browser.

Agent A (the learner) writes lessons into a notebook after each loss or draw and reads it before the next game.
Agent B (the control) never learns. The experiment measures whether Agent A's results improve over time.

**Status:** Phase 1 — sample game diaries made from real games.

## Try it
```
python arena/make_sample_diaries.py   # turn the games in samples/ into diaries
python tests/check_diaries.py         # check every diary move by move
```

## Folders
| Folder | What it is for |
|---|---|
| docs/ | The public replay website (GitHub Pages) |
| arena/ | The referee, players and game runner |
| prompts/ | Instructions given to the agents |
| notebook/ | Agent A's lesson notebook and its history |
| samples/ | Real games used for testing |
| tests/ | Automatic checks |
| engines/ | Local chess engine (not uploaded) |
