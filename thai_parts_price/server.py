"""Tiny local web server: one HTML page + POST /api/plan.  Standard library only."""
import json
import os
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

from . import service, shipping

WEB = os.path.join(os.path.dirname(__file__), "web")
# only these files are ever served (no path from the URL is ever joined to the disk)
STATIC = {
    "/": ("index.html", "text/html; charset=utf-8"),
    "/index.html": ("index.html", "text/html; charset=utf-8"),
    "/shipping": ("shipping.html", "text/html; charset=utf-8"),
    "/style.css": ("style.css", "text/css; charset=utf-8"),
    "/app.js": ("app.js", "text/javascript; charset=utf-8"),
    "/shipping.js": ("shipping.js", "text/javascript; charset=utf-8"),
}
MAX_BODY = 262_144


class Handler(BaseHTTPRequestHandler):
    server_version = "thai-parts-price"

    def _send(self, code, body: bytes, ctype: str):
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Content-Length", str(len(body)))
        self.send_header("Cache-Control", "no-store")
        self.send_header("X-Content-Type-Options", "nosniff")
        self.send_header("Content-Security-Policy", "frame-ancestors 'none'")
        self.end_headers()
        self.wfile.write(body)

    def _json(self, code, obj):
        self._send(code, json.dumps(obj, ensure_ascii=False).encode(), "application/json; charset=utf-8")

    def do_GET(self):
        path = self.path.split("?")[0]
        if path in STATIC:
            name, ctype = STATIC[path]
            with open(os.path.join(WEB, name), "rb") as f:
                self._send(200, f.read(), ctype)
        elif path == "/api/shipping":
            with open(shipping.RATES_PATH, "rb") as f:
                self._send(200, f.read(), "application/json; charset=utf-8")
        elif path == "/favicon.ico":
            self._send(204, b"", "image/x-icon")
        else:
            self._json(404, {"error": "not found"})

    def do_POST(self):
        if self.path not in ("/api/search", "/api/plan"):
            return self._json(404, {"error": "not found"})
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if n <= 0 or n > MAX_BODY:
                return self._json(413, {"error": "bad size"})
            body = json.loads(self.rfile.read(n).decode("utf-8"))
            if self.path == "/api/search":
                result = service.search_products(body.get("query"))
            else:
                result = service.plan_from_picks(body.get("groups"))
        except (ValueError, KeyError, AttributeError, TypeError, UnicodeDecodeError):
            return self._json(400, {"error": "bad request"})
        except Exception as e:  # a shop being down must not crash the server
            return self._json(502, {"error": f"failed: {type(e).__name__}"})
        self._json(200, result)

    def log_message(self, fmt, *args):
        pass


def serve(port: int = 4027, host: str = "127.0.0.1"):
    srv = ThreadingHTTPServer((host, port), Handler)
    print(f"http://{host}:{port}/   (Ctrl+C to stop)")
    try:
        srv.serve_forever()
    except KeyboardInterrupt:
        pass
