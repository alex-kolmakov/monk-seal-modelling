"""Serve the prototype and run the seal model on demand.

    uv run python prototype/serve.py        # then open http://localhost:8765

POST /api/simulate {"agents": 12, "seed": 42}  starts download + simulation in the background
GET  /api/status                                {"state": "idle|running|done|error", "message": ..., "error": ...}
Everything else is a static file from this directory (seals.json appears here after a run).
"""
import importlib
import json
import os
import threading
from functools import partial
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path

import simulate_forecast

HERE = Path(__file__).parent
status = {"state": "idle", "message": "", "error": None}
lock = threading.Lock()


def _work(agents: int, seed: int, desertas: bool, shelf: bool, leave_to_feed: bool, trips: bool = True) -> None:
    def say(msg: str) -> None:
        status["message"] = msg
    try:
        importlib.reload(simulate_forecast)  # pick up edits to the pipeline without restarting the server
        simulate_forecast.simulate(agents, seed, say, desertas, shelf, leave_to_feed, trips)
        status.update(state="done", message="Done", error=None)
    except Exception as e:  # shown in the page
        status.update(state="error", message="Failed", error=str(e)[-1500:])


class Handler(SimpleHTTPRequestHandler):
    def _json(self, obj, code=200):
        body = json.dumps(obj).encode()
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def end_headers(self):
        self.send_header("Cache-Control", "no-store")
        super().end_headers()

    def do_GET(self):
        if self.path.startswith("/api/status"):
            return self._json(status)
        return super().do_GET()

    def do_POST(self):
        if not self.path.startswith("/api/simulate"):
            return self._json({"error": "not found"}, 404)
        n = int(self.headers.get("Content-Length") or 0)
        body = json.loads(self.rfile.read(n) or b"{}")
        with lock:
            if status["state"] == "running":
                return self._json(status, 409)
            status.update(state="running", message="Starting", error=None)
        threading.Thread(target=_work, args=(int(body.get("agents", 12)), int(body.get("seed", 42)), bool(body.get("desertas", True)), bool(body.get("shelf", True)), bool(body.get("leave_to_feed", True)), bool(body.get("trips", True))), daemon=True).start()
        self._json(status)


if __name__ == "__main__":
    host = os.environ.get("PROTOTYPE_HOST", "127.0.0.1")  # set to the Tailscale IP to reach it from another device
    srv = ThreadingHTTPServer((host, 8765), partial(Handler, directory=str(HERE)))
    print(f"http://{host}:8765")
    srv.serve_forever()
