"""
The Claude agent: a player whose moves come from Claude, run through
Claude Code on your Claude Pro plan (never the paid API).

Each move is one short, separate request:  claude -p ... --tools ""
(its answer is streamed, so the live view can show the thought as it is written)
- No tools: the agent can only think and answer (no files, no web, no engine).
- Our own short instructions replace Claude Code's long default ones, and
  extras (connected apps, skills, plugins) are switched off. This keeps every
  request small so it uses as little of your allowance as possible.
"""

import json
import os
import re
import shutil
import subprocess
import tempfile
import threading
import time
from pathlib import Path

import chess

from players import Player, Suggestion, Turn

ROOT = Path(__file__).resolve().parent.parent
PROMPTS = ROOT / "prompts"
CALL_LOG = ROOT / "logs" / "claude_calls.jsonl"

# Signs that the paid API would be used instead of the Pro plan.
PAID_API_VARIABLES = ["ANTHROPIC_API_KEY", "ANTHROPIC_AUTH_TOKEN"]


class AgentUnavailable(Exception):
    """Claude could not answer (e.g. the Pro plan usage limit was reached).
    The game can be continued later from where it stopped."""


def check_no_paid_api() -> None:
    """Refuses to run if a paid API key is set on this computer."""
    found = [v for v in PAID_API_VARIABLES if os.environ.get(v)]
    if found:
        raise SystemExit(
            f"Stopped: {', '.join(found)} is set on this computer, so Claude Code would "
            "bill the paid API instead of your Pro plan. Remove it and try again.")


def board_diagram(board: chess.Board) -> str:
    """The board as text, with rank numbers and file letters."""
    rows = str(board).splitlines()
    lines = [f"{8 - i} {row}" for i, row in enumerate(rows)]
    lines.append("  a b c d e f g h")
    return "\n".join(lines)


def move_history(board: chess.Board) -> str:
    """The moves so far in normal chess notation, e.g. '1. e4 e5 2. Nf3'."""
    if not board.move_stack:
        return "(none yet: this is the first move)"
    return board.root().variation_san(board.move_stack)


class ClaudeAgent(Player):
    kind = "claude"

    def __init__(self, name: str = "Claude", model: str = "sonnet", effort: str = "low",
                 notebook_path: Path | None = None, mistakes=None, learner: bool | None = None,
                 timeout: int = 1800):
        self.name = name
        self.model = model
        self.effort = effort
        self.notebook_path = notebook_path   # Magnus's notebook (Hans has none)
        self.mistakes = mistakes             # Magnus's mistake library (notebook.MistakeLibrary)
        self.learner = bool(notebook_path) if learner is None else learner
        self.timeout = timeout               # seconds; long, because "max" effort can think for minutes
        self.system_prompt = (PROMPTS / "move_system.txt").read_text(encoding="utf-8")
        self.turn_template = (PROMPTS / "move_turn.txt").read_text(encoding="utf-8")
        # The move protocol: Hans's is Magnus's without the notebook step.
        protocol = "protocol_learner.txt" if self.learner else "protocol_control.txt"
        self.protocol = (PROMPTS / protocol).read_text(encoding="utf-8").strip()
        self.expected_model = None           # the experiment's model; stop if Claude Code switches to another
        self.last_usage = None
        self.game_id = None                  # set by the arbiter, for the call log
        self.on_text = None                  # called with the answer so far while Claude writes
        check_no_paid_api()

    def info(self) -> dict:
        return {"name": self.name, "type": self.kind, "model": self.model,
                "effort": self.effort, "notebook": bool(self.notebook_path),
                "mistake_library": bool(self.mistakes)}

    # ---------- Building the message ----------

    def turn_message(self, turn: Turn) -> str:
        board = turn.board
        white = turn.color == "white"
        notebook = mistakes = ""
        if self.learner:
            text = ""
            if self.notebook_path and self.notebook_path.exists():
                lines = self.notebook_path.read_text(encoding="utf-8").splitlines()
                text = "\n".join(line for line in lines if not line.startswith("#")).strip()  # no heading
            notebook = (f"\nYour notebook (rules you wrote after your earlier games):\n{text}\n" if text
                        else "\nYour notebook: (empty so far: you have not studied any games yet)\n")
            past = self.mistakes.text(board, turn.color) if self.mistakes else ""
            if past:
                mistakes = f"\nYour own past mistakes in positions like this one (from your mistake library):\n{past}\n"
        feedback = ""
        if turn.feedback:
            notes = "\n".join(f"- {f}" for f in turn.feedback)
            feedback = (f"\nThe arbiter refused your previous answer:\n{notes}\n"
                        "Choose a move copied exactly from the list of legal moves.\n")
        dots = "." if white else "..."
        return self.turn_template.format(
            color="White" if white else "Black",
            color_short="White" if white else "Black",
            piece_case="UPPERCASE" if white else "lowercase",
            move_label=f"move {board.fullmove_number}{dots}",
            board=board_diagram(board),
            fen=board.fen(),
            history=move_history(board),
            legal_moves=", ".join(sorted(board.san(m) for m in board.legal_moves)),
            notebook=notebook,
            mistakes=mistakes,
            feedback=feedback,
            protocol=self.protocol,
        )

    # ---------- Asking Claude ----------

    def ask(self, message: str, system_prompt: str | None = None) -> str:
        """Sends one request to Claude Code and returns Claude's answer text."""
        env = {k: v for k, v in os.environ.items() if k not in PAID_API_VARIABLES}
        program = shutil.which("claude")
        if not program:
            raise SystemExit("Stopped: Claude Code ('claude') was not found on this computer.")
        command = [
            program, "-p",   # the message itself is sent through the input (below)
            # The answer arrives piece by piece, so the live view can show it growing.
            "--output-format", "stream-json", "--verbose", "--include-partial-messages",
            "--model", self.model,
            "--effort", self.effort,
            "--tools", "",
            "--system-prompt", system_prompt or self.system_prompt,
            "--safe-mode", "--strict-mcp-config", "--no-session-persistence",
        ]
        started = time.time()
        timed_out = threading.Event()
        # The message is sent through the input, from a file that is complete before
        # Claude Code starts. (On the command line, or written in while it was
        # already starting, the message was sometimes lost and Claude replied
        # "What would you like to work on today?".)
        # Run from an empty folder so no project files are picked up.
        with tempfile.TemporaryDirectory() as empty, tempfile.TemporaryDirectory() as box, \
                tempfile.TemporaryFile("w+", encoding="utf-8") as errors:
            message_file = Path(box) / "message.txt"
            message_file.write_text(message, encoding="utf-8")
            with open(message_file, encoding="utf-8") as stdin:
                process = subprocess.Popen(command, cwd=empty, env=env, stdin=stdin,
                                           stdout=subprocess.PIPE, stderr=errors, text=True, encoding="utf-8")
            timer = threading.Timer(self.timeout, lambda: (timed_out.set(), process.kill()))
            timer.start()
            try:
                data = self.read_stream(process.stdout)
                process.wait()
            finally:
                timer.cancel()
            errors.seek(0)
            error_text = errors.read()
        if timed_out.is_set():
            raise AgentUnavailable(f"Claude did not answer within {self.timeout} seconds.")
        if data is None:
            raise AgentUnavailable("Claude Code gave an unreadable answer: " + error_text.strip()[:300])
        if data.get("is_error"):
            raise AgentUnavailable("Claude Code reported a problem: " + str(data.get("result"))[:300])

        models = list((data.get("modelUsage") or {}).keys())
        if self.expected_model and models and self.expected_model not in models:
            raise AgentUnavailable(
                f"Claude Code answered with a different model ({', '.join(models)}) than the experiment's "
                f"{self.expected_model}. The game is saved; check the model before continuing.")
        usage = data.get("usage") or {}
        self.last_usage = {
            "input_tokens": usage.get("input_tokens", 0)
            + usage.get("cache_read_input_tokens", 0) + usage.get("cache_creation_input_tokens", 0),
            "output_tokens": usage.get("output_tokens", 0),
            "seconds": round(time.time() - started, 1),
        }
        self.log_call(data)
        return data.get("result") or ""

    def read_stream(self, lines) -> dict | None:
        """Reads Claude Code's output line by line. Each new piece of the answer is
        passed to on_text (the whole answer so far); returns the final summary
        (answer, usage), or None if there was none."""
        text, result = "", None
        for line in lines:
            try:
                event = json.loads(line)
            except json.JSONDecodeError:
                continue
            if event.get("type") == "stream_event":
                delta = (event.get("event") or {}).get("delta") or {}
                if delta.get("type") == "text_delta":
                    text += delta.get("text", "")
                    if self.on_text:
                        self.on_text(text)
            elif event.get("type") == "result":
                result = event
        return result

    def log_call(self, data: dict) -> None:
        """Keeps a record of every request, to measure how much allowance games use."""
        CALL_LOG.parent.mkdir(parents=True, exist_ok=True)
        entry = {"time": time.strftime("%Y-%m-%d %H:%M:%S"), "game": self.game_id,
                 "agent": self.name, "model": list((data.get("modelUsage") or {}).keys()),
                 **self.last_usage, "api_equivalent_usd": data.get("total_cost_usd")}
        with open(CALL_LOG, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry) + "\n")

    # ---------- Playing ----------

    def suggest(self, turn: Turn) -> Suggestion:
        return self.read_answer(self.ask(self.turn_message(turn)))

    @staticmethod
    def read_answer(answer: str) -> Suggestion:
        """Finds the MOVE and THOUGHT lines, tolerating extra decoration such as
        **MOVE:** Nf3, `Nf3`, "Move: Nf3." or a thought spread over lines."""
        # The word MOVE, then a colon (decorations allowed around it), then the move.
        # "MOVE:" in capitals first, so a thought like "a good move: develop" is not read as a move.
        pattern = r"\bMOVE\b[\s*_`]*:[\s*_`]*([^\s*`\"']+)"
        move = re.search(pattern, answer) or re.search(pattern, answer, re.I)
        # The thought runs until "MOVE:" (or "RULES:") in capitals, on its own line or at
        # the end of the thought's line (Claude writes its thought first).
        thought = re.search(r"\bTHOUGHT\b[\s*_`]*:[\s*_`]*(.+?)(?=(?-i:[\s*_`]*\b(?:MOVE|RULES)\b[\s*_`]*:)|\Z)",
                            answer, re.I | re.S)
        # Magnus's RULES line: the notebook rules he checked ("none" = an empty list).
        rules = re.search(r"\bRULES\b[\s*_`]*:[\s*_`]*([^\n]*)", answer)
        extra = {"rules": [int(n) for n in re.findall(r"\d+", rules.group(1))]} if rules else {}
        move_text = move.group(1).rstrip(".,;") if move else ""
        if thought:
            thought_text = " ".join(thought.group(1).replace("*", "").split())
        else:
            thought_text = " ".join(answer.split())[:300]
        return Suggestion(move_text, thought_text or "(no thought given)", "claude", raw=answer, extra=extra)
