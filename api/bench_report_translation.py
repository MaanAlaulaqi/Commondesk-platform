"""Time the real case endpoint against a loopback worker using one invented incident."""

import argparse
import json
import os
import tempfile
import time
from pathlib import Path
from unittest.mock import patch


def benchmark(port):
    with (
        tempfile.TemporaryDirectory() as temp,
        patch.dict(
            os.environ,
            {
                "DATA_DIR": temp,
                "DATABASE_URL": "sqlite:///" + temp + "/pilot.sqlite",
                "TRANSLATOR_URL": f"http://127.0.0.1:{port}",
                "INDEX_ENABLED": "0",
            },
        ),
    ):
        from fastapi.testclient import TestClient
        from main import app

        invented = "At gate four the lamp is broken. The lamp at gate five still works."
        timings = {}
        with (
            TestClient(app) as api,
            patch(
                "main.jobs.worker",
                return_value={
                    "intent": "complaint",
                    "category": "lighting",
                    "urgency": "low",
                    "version": "synthetic-fixture",
                },
            ),
        ):
            intake = {"language": "en", "text": invented}
            receipt = api.post("/api/proposal", json=intake).json()
            item = api.post(
                "/api/cases",
                json={**intake, "proposal_digest": receipt["proposal_digest"]},
            ).json()
            case_path = "/api/cases/" + item["id"]
            for stage in ("uncached", "cached", "outage"):
                if stage == "outage":
                    os.environ.pop("TRANSLATOR_URL")
                start = time.monotonic()
                result = api.post(
                    case_path + "/translation",
                    json={"source": "live", "target_language": "ar"},
                )
                duration = time.monotonic() - start
                body = result.json()
                timings[stage] = {
                    "milliseconds": round(duration * 1000, 2),
                    "status": result.status_code,
                }
                if stage != "outage":
                    assert (
                        result.is_success
                        and body["kind"] == "machine"
                        and body["text"].strip()
                    )
                    assert body["cached"] == (stage == "cached")
                    timings[stage].update(
                        model_revision=body["model_revision"], cached=body["cached"]
                    )
                else:
                    assert result.status_code == 503
                    timings[stage]["original_available"] = (
                        api.get(case_path).json()["original_text"] == invented
                    )
                    assert timings[stage]["original_available"]
        return {
            "environment": "isolated SQLite, TestClient, loopback worker",
            "source": "invented test incident",
            "direction": "en:ar",
            "samples": timings,
        }


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("worker_port", type=int)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = json.dumps(benchmark(args.worker_port), indent=2)
    print(result)
    if args.output:
        args.output.write_text(result + "\n")
