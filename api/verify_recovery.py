"""Exercise a saved case across a worker outage and an API restart in an empty local database."""

import argparse
import os
import socket
import subprocess
import sys
import tempfile
import threading
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
import time
import uuid
from contextlib import contextmanager
from pathlib import Path
from urllib.parse import urlsplit

import httpx
from sqlalchemy import create_engine, select

from db import cases, queue


@contextmanager
def server(env, port, hard_stop=False):
    with subprocess.Popen(
        [
            sys.executable,
            "-m",
            "uvicorn",
            "main:app",
            "--host",
            "127.0.0.1",
            "--port",
            str(port),
        ],
        cwd=Path(__file__).parent,
        env=env,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    ) as proc:
        try:
            root = f"http://127.0.0.1:{port}/api/"
            with httpx.Client(base_url=root, timeout=60) as client:
                deadline = time.monotonic() + 20
                while time.monotonic() < deadline:
                    if proc.poll() is not None:
                        raise RuntimeError("Test API exited")
                    try:
                        if client.get("ready").status_code == 200:
                            break
                    except httpx.HTTPError:
                        pass
                    time.sleep(0.1)
                else:
                    raise TimeoutError("Test API did not start")
                yield client
        finally:
            if hard_stop:
                proc.kill()
            else:
                proc.terminate()
            proc.wait(timeout=15)


def verify(directory, worker_url, local_pg, qdrant_url=None):
    # Optional empty Postgres database lets the same regression run against either supported store.
    url = local_pg or f"sqlite:///{directory}/recovery.sqlite"
    if local_pg and urlsplit(local_pg).hostname not in (
        "127.0.0.1",
        "localhost",
        "::1",
    ):
        raise ValueError("Provide a dedicated empty local database")
    db = create_engine(url.replace("postgresql://", "postgresql+psycopg://", 1))
    with socket.socket() as s:
        s.bind(("127.0.0.1", 0))
        port = s.getsockname()[1]
    env = dict(
        os.environ,
        DATABASE_URL=url,
        WORKER_URL="http://127.0.0.1:1",
        INDEX_ENABLED="1",
        DATA_DIR=directory,
    )
    with server(env, port) as client:
        assert client.get("cases").json()["total"] == 0, (
            "Use an empty recovery database"
        )
        body = {
            "text": "Demonstration drain is blocked",
            "language": "en",
            "district": "recovery-" + uuid.uuid4().hex,
            "idempotency_key": "test-case",
        }
        response = client.post("cases", json=body)
        response.raise_for_status()
        cid = response.json()["id"]
        for _ in range(50):
            with db.connect() as conn:
                attempts = conn.scalar(
                    select(queue.c.attempts).where(queue.c.case_id == cid)
                )
            if attempts:
                break
            time.sleep(0.2)
        assert (
            attempts and client.get("cases/" + cid).json()["index_status"] == "pending"
        )
    # Interrupt an active lease while a fake inference worker is holding the HTTP request.
    claimed = threading.Event()
    release = threading.Event()

    class HeldRequest(BaseHTTPRequestHandler):
        def do_POST(self):
            claimed.set()
            release.wait(60)

        def log_message(self, *args):
            pass

    with ThreadingHTTPServer(("127.0.0.1", 0), HeldRequest) as stalled:
        threading.Thread(target=stalled.serve_forever, daemon=True).start()
        env["WORKER_URL"] = f"http://127.0.0.1:{stalled.server_port}"
        try:
            with server(env, port, hard_stop=True):
                assert claimed.wait(15), "Missing in-flight indexing request"
                with db.connect() as conn:
                    assert conn.scalar(
                        select(queue.c.lease).where(queue.c.case_id == cid)
                    )
        finally:
            release.set()
            stalled.shutdown()
    restart_at = time.monotonic()
    env["WORKER_URL"] = worker_url
    with server(env, port) as client:
        assert client.post("cases", json=body).json()["id"] == cid

        def wait_index():
            for _ in range(120):
                if client.get("cases/" + cid).json().get("index_status") == "indexed":
                    return
                time.sleep(1)
            raise TimeoutError("Case still pending")

        wait_index()
        recovery_seconds = round(time.monotonic() - restart_at, 1)
        # Recreate the same durable job; vector upsert uses the stable source/case identifier.
        with db.begin() as conn:
            conn.execute(
                cases.update().where(cases.c.id == cid).values(index_status="pending")
            )
            conn.execute(
                queue.insert().values(case_id=cid, revision=1, attempts=0, available=0)
            )
        wait_index()
        results = client.post(
            "search",
            json={
                "text": "blocked drain",
                "source": "live",
                "filters": {"district": body["district"]},
            },
        ).json()
        assert [r["id"] for r in results["items"]] == [cid], results
        assert client.get("cases", params={"source": "live"}).json()["total"] == 1
        assert len(client.get("cases/" + cid).json()["events"]) == 1
        if qdrant_url:
            query = {
                "filter": {"must": [{"key": "id", "match": {"value": cid}}]},
                "exact": True,
            }
            count = httpx.post(
                qdrant_url.rstrip("/") + "/collections/commondesk_live_v1/points/count",
                json=query,
            )
            count.raise_for_status()
            assert count.json()["result"]["count"] == 1
        print(
            f"Verified {cid}: empty start, failed-index retry, crash during active lease, "
            f"recovered in {recovery_seconds}s, one receipt and one result after replay. "
            f"Exact Qdrant point count {'verified' if qdrant_url else 'not requested'}."
        )
    db.dispose()
    return cid


if __name__ == "__main__":
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--worker", default="http://127.0.0.1:8001")
    p.add_argument(
        "--local-postgres", help="URL of an existing, empty local-only test database"
    )
    p.add_argument("--qdrant", help="Local Qdrant service URL for an exact point count")
    args = p.parse_args()
    with tempfile.TemporaryDirectory() as tmp:
        verify(tmp, args.worker, args.local_postgres, args.qdrant)
