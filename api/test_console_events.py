"""Consent-independent ordinary console logging, with fixed schemas and per-process limits."""

import io
import json
import logging
import os
import tempfile
import unittest
import uuid
from contextlib import contextmanager
from unittest.mock import patch

from fastapi.testclient import TestClient


class ConsoleTest(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.temp = tempfile.TemporaryDirectory()
        os.environ.update(
            INDEX_ENABLED="0", DATABASE_URL=f"sqlite:///{cls.temp.name}/cases.sqlite"
        )
        from main import app
        from console_events import logger

        cls.client = TestClient(app).__enter__()
        cls.logger = logger

    @classmethod
    def tearDownClass(cls):
        cls.client.__exit__(None, None, None)
        cls.temp.cleanup()

    @contextmanager
    def capture(self):
        stream = io.StringIO()
        handler = logging.StreamHandler(stream)
        self.logger.addHandler(handler)
        try:
            yield stream
        finally:
            self.logger.removeHandler(handler)

    def test_correlation(self):
        cid = str(uuid.uuid4())
        headers = {"X-Correlation-ID": cid, "X-UI-Language": "ar"}
        with self.capture() as out:
            self.assertEqual(
                self.client.post(
                    "/api/ui-events", headers=headers, json={"action": "report_open"}
                ).status_code,
                204,
            )
            detail = self.client.get(
                "/api/cases/secret-case?needle=secret-value",
                headers={**headers, "X-Forwarded-For": "192.0.2.111"},
            )
            self.assertEqual(detail.status_code, 404)
            self.assertEqual(detail.headers["X-Correlation-ID"], cid)
        rows = [json.loads(line) for line in out.getvalue().splitlines()]
        self.assertTrue(all(r["uiLanguage"] == "ar" for r in rows))
        self.assertEqual([r["event"] for r in rows], ["ui", "operation", "api"])
        self.assertTrue(
            all(r["correlationId"] == cid and r["durationMs"] >= 0 for r in rows)
        )
        self.assertEqual(
            (rows[0]["action"], rows[1]["function"], rows[1]["outcome"]),
            ("report_open", "detail", "error"),
        )
        self.assertEqual(
            (rows[2]["route"], rows[2]["status"]), ("/api/cases/{cid}", 404)
        )
        self.assertNotRegex(out.getvalue(), "secret|192.0.2.111")
        self.assertTrue(logging.getLogger("uvicorn.access").disabled)

    def test_ids_and_fields(self):
        cid = str(uuid.uuid4())
        with self.capture() as out:
            bads = (
                "fake-secret-id",
                str(uuid.uuid1()),
                "urn:uuid:" + cid,
                cid + ", " + cid,
            )
            for value in bads:
                reply = self.client.get(
                    "/api/health", headers={"X-Correlation-ID": value}
                )
                self.assertEqual(reply.status_code, 200)
                self.assertEqual(
                    uuid.UUID(reply.headers["X-Correlation-ID"]).version, 4
                )
                self.assertNotEqual(value, reply.headers["X-Correlation-ID"])
                self.assertEqual(
                    self.client.post(
                        "/api/ui-events",
                        headers={"X-Correlation-ID": value},
                        json={"action": "control_button"},
                    ).status_code,
                    422,
                )
            headers = {"X-Correlation-ID": cid}
            invalid = [
                {"action": "sensitive-input"},
                {"action": "control_button", "body": "sensitive-input"},
                {"action": ["control_button"]},
                {"action": None},
                "sensitive-input",
            ]
            for value in invalid:
                response = self.client.post(
                    "/api/ui-events", headers=headers, json=value
                )
                self.assertEqual(response.status_code, 422)
                self.assertNotIn("sensitive-input", response.text)
            self.assertEqual(
                self.client.post(
                    "/api/ui-events", headers=headers, json={"action": "x" * 1000}
                ).status_code,
                413,
            )
            self.assertEqual(
                self.client.post(
                    "/api/ui-events?secret=private",
                    headers=headers,
                    json={"action": "control_button"},
                ).status_code,
                422,
            )
            self.assertEqual(
                self.client.get("/secret-unmatched-route").status_code, 404
            )
        self.assertNotRegex(
            out.getvalue(),
            r"sensitive-input|fake-secret-id|secret-unmatched-route|private|urn:uuid",
        )
        self.assertTrue(
            all(
                "action" not in json.loads(line) for line in out.getvalue().splitlines()
            )
        )

    def test_language_allowlist(self):
        values = [
            "en",
            "ar",
            "th",
            "hi",
            "ur",
            "ar-AE",
            "AR",
            "unsupported-value",
            None,
        ]
        with self.capture() as out:
            for value in values:
                headers = {"Accept-Language": "private-preference"}
                if value is not None:
                    headers["X-UI-Language"] = value
                self.client.get("/api/health", headers=headers)
            self.client.get(
                "/api/health",
                headers=[("X-UI-Language", "ar"), ("X-UI-Language", "en")],
            )
        self.assertEqual(
            [json.loads(line)["uiLanguage"] for line in out.getvalue().splitlines()],
            values[:5] + [None] * 5,
        )
        self.assertNotRegex(
            out.getvalue(), "unsupported-value|private-preference|ar-AE"
        )

    def test_browser_preflight(self):
        response = self.client.options(
            "/api/ui-events",
            headers={
                "Origin": "http://localhost:5173",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-Correlation-ID,X-UI-Language,Content-Type",
            },
        )
        self.assertEqual(response.status_code, 200)
        self.assertEqual(
            response.headers["Access-Control-Allow-Origin"], "http://localhost:5173"
        )
        self.assertIn(
            "x-correlation-id", response.headers["Access-Control-Allow-Headers"].lower()
        )
        self.assertIn(
            "x-ui-language", response.headers["Access-Control-Allow-Headers"].lower()
        )
        denied = self.client.options(
            "/api/ui-events",
            headers={
                "Origin": "https://untrusted.invalid",
                "Access-Control-Request-Method": "POST",
                "Access-Control-Request-Headers": "X-Correlation-ID",
            },
        )
        self.assertNotIn("Access-Control-Allow-Origin", denied.headers)

    def test_storm(self):
        with patch("console_events.MAX_EVENTS_PER_MINUTE", 0), self.capture() as out:
            reply = self.client.post(
                "/api/ui-events",
                headers={"X-Correlation-ID": str(uuid.uuid4())},
                json={"action": "report_open"},
            )
            self.assertEqual(reply.status_code, 429)
            self.assertEqual(out.getvalue(), "")
            self.assertEqual(self.client.get("/api/health").status_code, 200)


if __name__ == "__main__":
    unittest.main()
