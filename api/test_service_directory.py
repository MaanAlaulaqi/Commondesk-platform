"""Run with PYTHONPATH=api:. in a fresh process. Every case and provider here is invented."""

import json
import os
from pathlib import Path
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

TEMP = tempfile.TemporaryDirectory()
root = Path(TEMP.name)
os.environ.update(
    DATA_DIR=str(root), DATABASE_URL=f"sqlite:///{root}/test.sqlite", INDEX_ENABLED="0"
)
from db import cases, engine, migrate
from main import app
from service_directory import private_options, service_options
from worker.grounding import answer
from worker.intake import proposal as intake_proposal

FIXTURES = json.loads(
    Path(__file__).with_name("service-directory.example.json").read_text()
)
FIXTURES = [{**f, "enabled": True} for f in FIXTURES]
PLUMBER, ELECTRIC = (f["id"] for f in FIXTURES)


class DirectoryTest(unittest.TestCase):
    def setUp(self):
        self.path = root / "directory.json"
        self.path.write_text(json.dumps(FIXTURES))
        env = patch.dict(os.environ, {"SERVICE_CATALOG_PATH": str(self.path)})
        env.start()
        self.addCleanup(env.stop)

    def test_catalog_and_scope(self):
        row = dict(
            source="live",
            intent="complaint",
            service_context="private_premises",
            text="Fixture",
            proposal={},
            suggested_urgency="low",
            final_urgency=None,
        )
        for cat, expected in (
            ("private_plumbing", PLUMBER),
            ("private_electrical", ELECTRIC),
        ):
            self.assertEqual([x["id"] for x in service_options(cat, row)], [expected])
            for changes in (
                {"intent": "feedback"},
                {"intent": "suggestion"},
                {"source": "archive"},
                {"source": "seed"},
                {"service_context": "public_asset"},
                {"service_context": "emergency"},
                {"service_context": "unknown"},
                {"text": "A public drain"},
                {"text": "An exposed wire"},
                {"text": "ไฟไหม้"},
                {"proposal": {"urgency_reason": "reported_hazard_keyword"}},
                {"final_urgency": "high"},
            ):
                self.assertEqual(service_options(cat, {**row, **changes}), [])
        self.assertEqual(service_options("lighting", row), [])
        self.assertEqual(service_options("drainage", row), [])
        self.assertEqual(service_options("footpath", row), [])
        public = {**row, "service_context": "unknown"}
        self.assertEqual(
            service_options("transit", public)[0]["kind"], "public_authority"
        )
        seed = {
            **public,
            "source": "seed",
            "proposal": {"category": "footpath", "service_options": []},
        }
        self.assertEqual(service_options("transit", seed), [])
        self.assertEqual(service_options("footpath", seed), [])
        seed["proposal"]["service_options"] = ["dubai_rta_madinati"]
        self.assertEqual(
            service_options("footpath", seed)[0]["id"], "dubai_rta_madinati"
        )
        self.assertEqual(service_options("transit", seed), [])
        for config in (
            [{**FIXTURES[0], "enabled": False}],
            FIXTURES + FIXTURES,
            [{**FIXTURES[0], "url": "https://example.org"}],
            [{**FIXTURES[0], "fictional": False}],
            [{"id": "arbitrary"}],
        ):
            self.path.write_text(json.dumps(config))
            self.assertEqual(private_options("private_plumbing"), [])
        self.path.write_text(
            json.dumps([{**FIXTURES[0], "allowed_districts": ["Demo North"]}])
        )
        self.assertEqual(private_options("private_plumbing"), [])
        self.assertEqual(private_options("private_plumbing", "Demo South"), [])
        self.assertEqual(
            private_options("private_plumbing", " demo NORTH ")[0]["id"], PLUMBER
        )
        self.path.write_text("incomplete")
        self.assertEqual(private_options("private_plumbing"), [])

    def test_intake_category_does_not_establish_ownership(self):
        samples = [
            ("en", "The leaking tap needs attention", "private_plumbing"),
            ("ar", "يوجد مقبس كهربائي معطل", "private_electrical"),
            ("hi", "बिजली का सॉकेट टूट गया", "private_electrical"),
            ("ur", "ہمارا نل ٹپک رہا ہے", "private_plumbing"),
            ("th", "ก๊อกน้ำรั่วในครัว", "private_plumbing"),
        ]
        for language, text, category in samples:
            result = intake_proposal({"text": text, "language": language})
            self.assertEqual(result["category"], category)
            self.assertIsNone(result["service"])
        self.assertEqual(
            intake_proposal({"text": "The wall socket is sparking", "language": "en"})[
                "urgency"
            ],
            "high",
        )
        self.assertEqual(
            intake_proposal(
                {"text": "The streetlight and wall socket are broken", "language": "en"}
            )["category"],
            "unclassified",
        )

    def test_transaction_and_citations(self):
        proposal = dict(intent="complaint", category="unclassified", urgency="moderate")

        def remote(route, payload):
            self.assertEqual(route, "/answer")
            return answer(payload)

        with (
            TestClient(app) as client,
            patch("main.jobs.worker", return_value=proposal),
            patch("main.remote", side_effect=remote),
        ):
            case = client.post(
                "/api/cases", json={"text": "Synthetic fixture", "language": "en"}
            ).json()
            path = "/api/cases/" + case["id"]

            def review(**body):
                return client.post(path + "/review", json=body)

            def guidance(lang="en", question=""):
                return client.post(
                    "/api/answer",
                    json={
                        "kind": "guidance",
                        "case_id": case["id"],
                        "language": lang,
                        "question": question,
                    },
                ).json()

            self.assertEqual(guidance()["outcome"], "no_evidence")
            self.assertEqual(review(service=PLUMBER).status_code, 422)
            decision = review(
                service_context="private_premises",
                category="private_plumbing",
                expected_revision=1,
            ).json()
            self.assertEqual(decision["original_text"], case["original_text"])
            self.assertEqual(
                decision["service_options"][0]["kind"], "private_directory"
            )
            self.assertEqual(
                review(service=PLUMBER, expected_revision=1).status_code, 409
            )
            self.assertEqual(review(service=ELECTRIC).status_code, 422)
            chosen = review(
                service=PLUMBER, expected_revision=2, idempotency_key="one"
            ).json()
            self.assertEqual(chosen["service"], PLUMBER)
            self.assertEqual(
                review(
                    service=PLUMBER, expected_revision=2, idempotency_key="one"
                ).json()["revision"],
                3,
            )
            eid = chosen["service_event_id"]
            self.assertTrue(eid)
            event = next(e for e in chosen["events"] if e["event_id"] == eid)
            self.assertFalse(event["details"]["external_dispatch"])
            self.assertEqual(event["details"]["routing"]["selected"]["id"], PLUMBER)
            for lang in ("en", "ar", "th", "hi", "ur"):
                grounded = guidance(lang)
                self.assertEqual(grounded["outcome"], "guidance")
                self.assertEqual(grounded["citations"], [PLUMBER, eid])
                self.assertTrue(grounded["links"][1]["url"].endswith("?event=" + eid))
            self.assertEqual(guidance(question="Madinati")["outcome"], "no_evidence")
            self.path.write_text("[]")
            self.assertIsNone(client.get(path).json()["service"])
            listed = client.get("/api/cases", params={"ids":case["id"]}).json()["items"]
            self.assertIsNone(listed[0]["service"])
            self.assertEqual(guidance()["outcome"], "no_evidence")
            self.path.write_text(json.dumps(FIXTURES))
            corrected = review(
                category="lighting", service_context="public_asset"
            ).json()
            self.assertIsNone(corrected["service"])
            self.assertIsNone(corrected["service_event_id"])
            auto_clear = corrected["events"][-1]["details"]["routing"]
            self.assertEqual(auto_clear["previous"], PLUMBER)
            self.assertIsNone(auto_clear["selected"])
            self.assertEqual(guidance()["outcome"], "no_evidence")
            self.assertEqual(review(service=PLUMBER).status_code, 422)


if __name__ == "__main__":
    unittest.main()
