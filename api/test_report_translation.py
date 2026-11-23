"""Offline regression using an isolated SQLite store and synthetic HTTP fixtures."""

import hashlib
import json
import os
import tempfile
import threading
import time
import unittest
import uuid
from concurrent.futures import ThreadPoolExecutor
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from unittest.mock import patch
from urllib.parse import urlsplit

from fastapi.testclient import TestClient


class FixtureWorker(BaseHTTPRequestHandler):
    def log_message(self, *args):
        pass

    def do_GET(self):
        if self.headers.get("Authorization") != "Bearer test-only-secret":
            return self.send_error(401)
        self.reply({"model_revision": self.server.rev, "directions": self.server.dirs})

    def do_POST(self):
        if self.headers.get("Authorization") != "Bearer test-only-secret":
            return self.send_error(401)
        data = json.loads(self.rfile.read(int(self.headers["Content-Length"])))
        self.server.calls.append(data)
        time.sleep(0.15)
        self.reply(
            {
                "model_revision": self.server.response_revision or self.server.rev,
                "text": "synthetic translation",
            }
        )

    def reply(self, value):
        self.send_response(200)
        self.send_header("Content-Type", "application/json")
        self.end_headers()
        self.wfile.write(json.dumps(value).encode())


class TranslationTests(unittest.TestCase):
    def test_report_workflow(self):
        from db import cases, meta, report_translations, views
        from fastapi import HTTPException
        from main import app
        from report_translation import private_origin
        from sqlalchemy import create_engine

        with tempfile.TemporaryDirectory() as tmp:
            postgres = os.getenv("MT_TEST_POSTGRES_URL")
            if postgres:
                if urlsplit(postgres).hostname not in {"localhost", "127.0.0.1"}:
                    raise ValueError("Use a disposable loopback PostgreSQL server")
                schema = "mt_test_" + uuid.uuid4().hex
                admin = create_engine(postgres)
                with admin.begin() as conn:
                    conn.exec_driver_sql("CREATE SCHEMA " + schema)

                def remove_test_schema():
                    with admin.begin() as conn:
                        conn.exec_driver_sql("DROP SCHEMA " + schema + " CASCADE")
                    admin.dispose()

                self.addCleanup(remove_test_schema)
                engine = create_engine(
                    postgres, connect_args={"options": "-csearch_path=" + schema}
                )
            else:
                engine = create_engine("sqlite:///" + tmp + "/test.sqlite")
            meta.create_all(engine)
            server = ThreadingHTTPServer(("127.0.0.1", 0), FixtureWorker)
            server.rev, server.response_revision, server.dirs = "r1", None, ["en:th"]
            server.calls = []
            thread = threading.Thread(target=server.serve_forever, daemon=True)
            thread.start()
            self.addCleanup(server.server_close)
            self.addCleanup(server.shutdown)
            with (
                patch("db.engine", engine),
                patch("main.engine", engine),
                patch("report_translation.engine", engine),
                patch.dict(
                    os.environ, MT_INTERNAL_TOKEN="test-only-secret", TRANSLATOR_URL=f"http://127.0.0.1:{server.server_port}"
                ),
            ):
                api = TestClient(app)
                with engine.begin() as db:
                    row = {
                        "id": "made-up",
                        "incident_id": "one",
                        "source": "live",
                        "text": "Invented English report",
                        "language": "en",
                        "intent": "complaint",
                        "category": "lighting",
                        "status": "reported",
                        "suggested_urgency": "low",
                        "created_at": "2026-01-01",
                        "week_start": "2026-01-01",
                        "day": "2026-01-01",
                        "provenance": "test",
                        "evidence_origin": {},
                        "proposal": {},
                        "index_status": "pending",
                        "revision": 1,
                    }
                    db.execute(cases.insert().values(**row))
                    db.execute(
                        cases.insert().values(
                            **{**row, "id": "seed-one", "source": "seed"}
                        )
                    )
                    db.execute(
                        views.insert().values(
                            case_id="seed-one",
                            language="ar",
                            text="synthetic wording",
                            view_id="ar",
                        )
                    )

                def translate(lang="th", cid="made-up", source="live", **fields):
                    return api.post(
                        f"/api/cases/{cid}/translation",
                        json={"source": source, "target_language": lang, **fields},
                    )

                self.assertEqual(translate("en").json()["kind"], "original")
                self.assertEqual(
                    translate("ar", "seed-one", "seed").json()["kind"], "stored"
                )
                self.assertEqual(translate("ar").status_code, 422)
                self.assertEqual(translate(source="seed").status_code, 404)
                self.assertEqual(translate(text="arbitrary").status_code, 422)
                archive = {
                    "source": "archive",
                    "id": "0" * 24,
                    "evidence_available": False,
                }
                with patch("main.httpx.get") as get:
                    get.return_value.json.return_value = archive
                    self.assertEqual(
                        translate(cid=archive["id"], source="archive").status_code, 422
                    )
                self.assertFalse(server.calls)
                with ThreadPoolExecutor(max_workers=4) as pool:
                    replies = [
                        r.json() for r in pool.map(lambda _: translate(), range(4))
                    ]
                self.assertEqual(len(server.calls), 1)
                self.assertEqual(
                    set(server.calls[0]), {"text", "source_language", "target_language"}
                )
                self.assertEqual(sum(r["cached"] for r in replies), 3)
                self.assertTrue(
                    all(
                        r["kind"] == "machine" and r["model_revision"] == "r1"
                        for r in replies
                    )
                )
                server.dirs = []
                self.assertEqual(translate().status_code, 422)
                server.dirs = ["en:th"]
                server.rev = "r2"
                self.assertFalse(translate().json()["cached"])
                with engine.begin() as db:
                    db.execute(
                        cases.update()
                        .where(cases.c.id == "made-up")
                        .values(text="New synthetic incident wording")
                    )
                server.response_revision = "wrong"
                self.assertEqual(translate().status_code, 503)
                server.response_revision = None
                self.assertFalse(translate().json()["cached"])
                self.assertTrue(translate().json()["cached"])
                with engine.connect() as db:
                    self.assertEqual(
                        len(db.execute(report_translations.select()).all()), 3
                    )
                # A terminated worker may leave a lease; recovery uses the same key.
                with engine.begin() as db:
                    db.execute(
                        report_translations.update()
                        .where(
                            report_translations.c.source_digest
                            == hashlib.sha256(
                                b"New synthetic incident wording"
                            ).hexdigest(),
                            report_translations.c.model_revision == "r2",
                        )
                        .values(lease="abandoned", expires_at=0, text=None)
                    )
                self.assertFalse(translate().json()["cached"])
                self.assertTrue(translate().json()["cached"])
                for deadline in ("1", "invalid"):
                    with patch.dict(os.environ, TRANSLATOR_EXPIRES_AT=deadline):
                        self.assertEqual(translate().status_code, 422)
                        self.assertEqual(translate("ar", "seed-one", "seed").json()["kind"], "stored")
                with patch.dict(os.environ, TRANSLATOR_URL=""):
                    self.assertEqual(translate().status_code, 422)
                    self.assertEqual(translate("ar", "seed-one", "seed").json()["kind"], "stored")
                with patch.dict(os.environ, TRANSLATOR_URL="http://worker:8001"):
                    self.assertEqual(private_origin(), "http://worker:8001")
                with patch.dict(os.environ, TRANSLATOR_URL="https://example.org"):
                    with self.assertRaises(HTTPException):
                        private_origin()
                    self.assertEqual(translate().status_code, 503)
            engine.dispose()


if __name__ == "__main__":
    unittest.main()
