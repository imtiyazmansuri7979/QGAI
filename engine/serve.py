"""
serve.py — QGAI Dashboard Server (FIX #12)
──────────────────────────────────────────
Plain `python -m http.server` rejects POST requests, so the dashboard's
MODE toggle (/mode) and AI Feedback (/feedback) buttons silently failed.
This tiny server serves the dashboard files AND handles those two POSTs.

Run:  python serve.py        (or use serve.bat)
Open: http://localhost:8000/dashboard.html
"""
import json
import sys
import time
from http.server import SimpleHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from datetime import datetime, timezone
from console_colors import BLUE, BOLD, CYAN, DIM, GREEN, RED, YELLOW, enable_console_color, paint

ENGINE_DIR = Path(__file__).resolve().parent
LOGS_DIR   = ENGINE_DIR / "logs"
LOGS_DIR.mkdir(parents=True, exist_ok=True)

PORT = 8000


class QGAIHandler(SimpleHTTPRequestHandler):

    def __init__(self, *args, **kwargs):
        super().__init__(*args, directory=str(ENGINE_DIR), **kwargs)

    # FIX #B1: never let the browser cache dashboard files.
    # A stale cached dashboard.html kept running OLD JavaScript
    # (pre-FIX-D5, ev_r.toFixed-on-null crash) even after the file
    # on disk was already fixed. no-store forces a fresh copy on
    # every page load.
    def end_headers(self):
        self.send_header("Cache-Control", "no-store, must-revalidate")
        self.send_header("Pragma", "no-cache")
        self.send_header("Expires", "0")
        super().end_headers()

    # Silence per-request console spam for dashboard.json polling.
    # args[0] can be a non-string (e.g. HTTPStatus on errors) — str() it first.
    def log_message(self, fmt, *args):
        first = str(args[0]) if args else ""
        if "dashboard.json" not in first:
            msg = fmt % args
            color = GREEN if " 200 " in f" {msg} " else YELLOW
            if any(code in f" {msg} " for code in (" 400 ", " 404 ", " 500 ")):
                color = RED
            sys.stderr.write(
                f"{paint(self.address_string(), DIM)} - "
                f"{paint(self.log_date_time_string(), DIM)} - "
                f"{paint(msg, color)}\n"
            )

    def _read_json_body(self):
        try:
            length = int(self.headers.get("Content-Length", 0))
            raw = self.rfile.read(length) if length else b"{}"
            return json.loads(raw.decode("utf-8"))
        except Exception:
            return {}

    def _send_json(self, obj, code=200):
        body = json.dumps(obj).encode("utf-8")
        self.send_response(code)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):
        p = self.path.split("?")[0]
        # Serve dashboard.json with a few retries. On Windows the bridge's atomic
        # os.replace() briefly makes the file un-openable → PermissionError; a short
        # retry avoids spurious 404s / "Failed to fetch" on the dashboard.
        if p == "/logs/dashboard.json" or p.endswith("/dashboard.json"):
            fp = LOGS_DIR / "dashboard.json"
            data = None
            for _ in range(6):
                try:
                    data = fp.read_bytes()
                    break
                except (PermissionError, OSError):
                    time.sleep(0.05)
            if data is not None:
                try:
                    self.send_response(200)
                    self.send_header("Content-Type", "application/json")
                    self.send_header("Content-Length", str(len(data)))
                    self.end_headers()
                    self.wfile.write(data)
                except (ConnectionAbortedError, ConnectionResetError, BrokenPipeError):
                    pass  # browser refreshed / navigated away mid-response — harmless
                return
            # if still unreadable, fall through to default handling
        # GET /mode → current mode (handy for the dashboard on load)
        if p == "/mode":
            mode = "live"
            try:
                mp = LOGS_DIR / "mode.json"
                if mp.exists():
                    mode = json.loads(mp.read_text(encoding="utf-8")).get("mode", "live")
            except Exception:
                pass
            return self._send_json({"ok": True, "mode": mode})
        return super().do_GET()

    def do_POST(self):
        path = self.path.split("?")[0]

        # ── POST /mode {"mode": "live"|"monitor"} ─────────────
        if path == "/mode":
            data = self._read_json_body()
            mode = data.get("mode", "")
            if mode not in ("live", "monitor"):
                return self._send_json({"ok": False, "error": "mode must be live|monitor"}, 400)
            try:
                (LOGS_DIR / "mode.json").write_text(
                    json.dumps({"mode": mode}), encoding="utf-8")
                print(paint(f"  Mode set to: {mode}", CYAN + BOLD))
                return self._send_json({"ok": True, "mode": mode})
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 500)

        # ── POST /feedback {...} → append to logs/feedback.jsonl ──
        if path == "/feedback":
            data = self._read_json_body()
            data["server_ts"] = datetime.now(timezone.utc).isoformat()
            try:
                with open(LOGS_DIR / "feedback.jsonl", "a", encoding="utf-8") as f:
                    f.write(json.dumps(data, default=str) + "\n")
                return self._send_json({"ok": True})
            except Exception as e:
                return self._send_json({"ok": False, "error": str(e)}, 500)

        return self._send_json({"ok": False, "error": "unknown endpoint"}, 404)


if __name__ == "__main__":
    enable_console_color()
    print(paint("=" * 60, BLUE + BOLD))
    print(paint("  QGAI Dashboard Server", CYAN + BOLD))
    print(paint(f"  http://localhost:{PORT}/dashboard.html", GREEN + BOLD))
    print(paint("  POST /mode and /feedback are handled (FIX #12)", YELLOW + BOLD))
    print(paint("=" * 60, BLUE + BOLD))
    ThreadingHTTPServer(("0.0.0.0", PORT), QGAIHandler).serve_forever()
