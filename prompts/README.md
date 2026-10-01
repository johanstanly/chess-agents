# prompts — what the agents are told
The exact instructions sent to the AI agents, as plain text you can read. During the experiment they are locked: if one changes, the runner refuses to continue.

- `move_system.txt`, `move_turn.txt`: what Magnus and Hans are sent for every move. Magnus's message also contains his notebook and similar past mistakes.
- `protocol_learner.txt`: Magnus's 3-step move protocol (read the notebook; calculate at least 2 candidate moves and check them against the notebook; play the move).
- `protocol_control.txt`: Hans's protocol: the same, without the notebook step.
- `lessons_system.txt`, `lessons_turn.txt`: what Magnus is sent after every game, to rewrite his notebook.
