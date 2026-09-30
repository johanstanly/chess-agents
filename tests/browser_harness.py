"""
Runs a web page in a hidden (headless) Microsoft Edge browser and collects a
result that the page reports back. Used for automatic checks of the website.

How it works:
- A small local web server serves the website (docs/) plus test pages
  (tests/pages/, reachable at /__tests/...).
- A test page includes <img src="/__hold" hidden>. The browser treats the page
  as "still loading" until that picture arrives, and the server holds it back
  until the page sends its result to /__done. This gives slow things (like the
  chess engine starting up) time to finish.

Use from another script:   result = run_page("/__tests/stockfish.html")
"""

import http.server
import os
import shutil
import subprocess
import tempfile
import threading
from functools import partial
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DOCS = ROOT / "docs"
TEST_PAGES = ROOT / "tests" / "pages"

EDGE_PATHS = [
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
    r"C:\Program Files\Microsoft\Edge\Application\msedge.exe",
]


def find_browser() -> str:
    for p in EDGE_PATHS:
        if Path(p).exists():
            return p
    for name in ("msedge", "chrome", "chromium", "google-chrome"):
        found = shutil.which(name)
        if found:
            return found
    raise RuntimeError("No Edge or Chrome browser found for the automatic check.")


class _Handler(http.server.SimpleHTTPRequestHandler):
    done = threading.Event()
    result = None
    games_dir = None   # if set, the website's games/ folder is read from here
    hold_seconds = 90  # how long the page's /__hold request keeps the browser open

    def log_message(self, *args):  # keep the output quiet
        pass

    def translate_path(self, path):
        if path.startswith("/__tests/"):
            return str(TEST_PAGES / path[len("/__tests/"):].split("?")[0])
        if path.startswith("/games/") and _Handler.games_dir:
            return str(Path(_Handler.games_dir) / path[len("/games/"):].split("?")[0])
        return super().translate_path(path)

    def do_GET(self):
        if self.path.startswith("/__hold"):
            _Handler.done.wait(timeout=_Handler.hold_seconds)
            self.send_response(204)
            self.end_headers()
            return
        super().do_GET()

    def do_POST(self):
        if self.path.startswith("/__done"):
            length = int(self.headers.get("Content-Length", 0))
            _Handler.result = self.rfile.read(length).decode("utf-8")
            _Handler.done.set()
            self.send_response(200)
            self.end_headers()
            return
        self.send_error(404)


class _QuietServer(http.server.ThreadingHTTPServer):
    def handle_error(self, request, client_address):
        pass  # the browser closing a connection early is not a problem


def run_page(path: str, timeout: int = 120, screenshot: str | None = None,
             size: str = "1366,768", games_dir: Path | None = None) -> str:
    """Opens `path` in a hidden browser; returns the text the page reported.
    With `screenshot`, also saves a picture of the page to that file.
    With `games_dir`, the website shows the games in that folder instead."""
    _Handler.done.clear()
    _Handler.hold_seconds = timeout
    _Handler.result = None
    _Handler.games_dir = games_dir
    server = _QuietServer(
        ("127.0.0.1", 0), partial(_Handler, directory=str(DOCS)))
    port = server.server_address[1]
    threading.Thread(target=server.serve_forever, daemon=True).start()
    # A separate, temporary browser profile: without it, an Edge window you
    # already have open would take over the request and the test would get no result.
    profile = tempfile.mkdtemp(prefix="chess-agents-browser-")
    # Settings inherited from VS Code (itself built on Chromium, like Edge) make
    # Edge hand over to VS Code's crash reporter and quit at once, and a Windows
    # compatibility setting (__COMPAT_LAYER) does the same. Leave them out.
    env = {k: v for k, v in os.environ.items()
           if not k.upper().startswith(("CHROME_", "ELECTRON_", "VSCODE_", "__COMPAT_LAYER"))}
    try:
        subprocess.run(
            [find_browser(), "--headless=new", "--disable-gpu", "--no-first-run",
             f"--user-data-dir={profile}", "--no-default-browser-check",
             "--hide-scrollbars", f"--window-size={size}",
             f"--screenshot={screenshot}" if screenshot else "--dump-dom",
             f"http://127.0.0.1:{port}{path}"],
            capture_output=True, timeout=timeout, env=env)
    finally:
        server.shutdown()
        shutil.rmtree(profile, ignore_errors=True)
    return _Handler.result if _Handler.result is not None else "NO RESULT (page did not report)"
