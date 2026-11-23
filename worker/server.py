"""Internal HTTP service. CPU inference is serialized to bound memory and local store access."""

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import json
import logging
import os
from pathlib import Path
from threading import Lock

from .encoders import MODEL_DIR, PINS
from .grounding import answer
from .intake import proposal
from .search import Store, Unavailable
from .seed import publish


class Handler(BaseHTTPRequestHandler):
    server_version = "CommonDesk-worker/1"

    def reply(self, status, data):
        buf = json.dumps(data, ensure_ascii=False, allow_nan=False).encode()
        self.send_response(status)
        self.send_header("Content-Type", "application/json; charset=utf-8")
        self.send_header("Content-Length", str(len(buf)))
        self.end_headers()
        self.wfile.write(buf)

    def do_GET(self):
        try:
            if self.path in ("/health", "/healthz"):
                return self.reply(200, {"ok": True})
            if self.path in ("/ready", "/readyz"):
                for k, v in PINS.items():
                    if not all((MODEL_DIR / k / f).is_file() for f in v["sha256"]):
                        raise Unavailable("Missing model artifacts")
                with self.server.lock:
                    self.server.store.client.get_collections()
                return self.reply(200, {"ready": True})
            if self.path.startswith("/archive/"):
                with self.server.lock:
                    detail = self.server.store.archive_detail(
                        self.path.removeprefix("/archive/")
                    )
                return self.reply(200, detail)
            return self.reply(404, {"detail": "Unknown route"})
        except (ValueError, KeyError):
            return self.reply(404, {"detail": "Unknown archive case"})
        except Exception:
            return self.reply(503, {"detail": "Worker dependency unavailable"})

    def do_POST(self):
        try:
            n = int(self.headers.get("Content-Length", "0"))
            if not 0 < n <= 13 * 1024 * 1024:
                return self.reply(413, {"detail": "Invalid request size"})
            body = json.loads(self.rfile.read(n))
            if not isinstance(body, dict):
                raise ValueError("Expected JSON object")
            if self.path == "/proposal":
                result = proposal(body)
            elif self.path == "/answer":
                if (
                    body.get("kind") == "report"
                    and not body.get("reports")
                    and body.get("question")
                    and not body.get("case_id")
                ):
                    with self.server.lock:
                        hits = self.server.store.search(
                            dict(
                                text=body["question"],
                                source=body.get("source", "live"),
                                filters=body.get("filters"),
                                limit=1,
                            )
                        )
                    body["reports"] = hits["items"]
                result = answer(body)
            else:
                with self.server.lock:
                    if self.path == "/index":
                        result = self.server.store.index(body)
                    elif self.path == "/metadata":
                        result = self.server.store.metadata(body)
                    elif self.path == "/search":
                        result = self.server.store.search(body)
                    elif self.path == "/seed" and os.getenv("SEED_DIR"):
                        result = publish(
                            self.server.store, Path(os.environ["SEED_DIR"])
                        )
                    else:
                        return self.reply(404, {"detail": "Unknown route"})
            return self.reply(200, result)
        except (ValueError, KeyError, TypeError) as exc:
            return self.reply(422, {"detail": str(exc)[:180]})
        except Unavailable as exc:
            return self.reply(503, {"detail": str(exc)})
        except Exception as exc:
            logging.error(
                "Worker operation failed (%s on %s)", type(exc).__name__, self.path
            )
            return self.reply(503, {"detail": "Retrieval dependency unavailable"})

    # Logs deliberately omit query data and case evidence.
    def log_message(self, format, *args):
        return


def main():
    server = ThreadingHTTPServer(
        (os.getenv("HOST", "0.0.0.0"), int(os.getenv("PORT", "8001"))), Handler
    )
    server.lock = Lock()
    server.store = Store()
    try:
        server.serve_forever()
    finally:
        server.store.client.close()
        server.server_close()


if __name__ == "__main__":
    main()
