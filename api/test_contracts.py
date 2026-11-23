"""Regression checks for confirmation and cross-collection search using a disposable store."""
import os
import tempfile
import unittest
from unittest.mock import patch

from fastapi.testclient import TestClient

with tempfile.TemporaryDirectory() as temp:
    # Fixtures and dependency overrides belong exclusively to this process.
    os.environ["DATA_DIR"] = temp
    os.environ["INDEX_ENABLED"] = "0"
    os.environ["DATABASE_URL"] = f"sqlite:///{temp}/test.sqlite"
    from main import app
    from db import cases, engine
    from worker.grounding import answer

    class ContractTest(unittest.TestCase):
        def test_workflows(self):
            first = dict(intent="complaint", category="footpath", urgency="moderate", version="one")
            with TestClient(app) as api, patch("main.jobs.worker", return_value=first) as inference:
                intake = {"text":"Test footpath", "language":"en", "idempotency_key":"A"}
                digest = api.post("/api/proposal",json=intake).json()["proposal_digest"]
                confirmed = {**intake, "proposal_digest":digest}
                inference.return_value = {**first,"version":"two"}
                assert api.post("/api/cases",json=confirmed).status_code == 409
                assert api.get("/api/cases").json()["total"] == 0
                inference.return_value = first
                result = api.post("/api/cases",json=confirmed)
                assert result.status_code == 201, result.text
                live_id = result.json()["id"]
                inference.return_value = {**first,"version":"other"}
                assert api.post("/api/cases",json=confirmed).json()["id"] == live_id
                with engine.begin() as conn:
                    seed = dict(conn.execute(cases.select()).mappings().one())
                    seed.update(id="example",incident_id="example",source="seed",requested_key=None)
                    conn.execute(cases.insert().values(**seed))
                hits = [{"source":"seed","id":"example","score":0.9},{"source":"live","id":live_id,"score":0.8}]
                with patch("main.remote",return_value={"items":hits}) as worker:
                    result = api.post("/api/search",json={"text":"footpath","source":"all"})
                    assert [i["id"] for i in result.json()["items"]] == ["example",live_id]
                    assert worker.call_count == 1
                    assert worker.call_args.args[1]["source"] == "all"
                assert api.get(f"/api/cases/{live_id}?source=seed").status_code == 404
                q = dict(kind="guidance",question="Madinati",source="live",reports=[])
                assert answer({**q,"case_id":live_id})["outcome"] == "no_evidence"
                assert answer(q)["outcome"] == "guidance"
    if __name__ == "__main__":
        unittest.main()
