"""A single in-flight write per case; newer revisions share the same durable job."""

import base64
import logging
import os
import threading
import time
import uuid

import httpx
from sqlalchemy import case, select
from db import cases, engine, insert_for, media, queue
from store import summary

log = logging.getLogger("uvicorn.error")
WORKER_URL = os.environ.get("WORKER_URL", "http://127.0.0.1:8001").rstrip("/")


def worker(path, payload, timeout=60):
    r = httpx.post(WORKER_URL + path, json=payload, timeout=timeout)
    r.raise_for_status()
    return r.json()


def enqueue(conn, cid, rev):
    stmt = insert_for(queue).values(
        case_id=cid, revision=rev, attempts=0, available=0, lease=None
    )
    # A newer revision must not race an older vector write. Keep an active writer's lease.
    conn.execute(
        stmt.on_conflict_do_update(
            index_elements=[queue.c.case_id],
            set_={
                "revision": rev,
                "attempts": 0,
                "available": case(
                    (queue.c.lease.is_(None), 0), else_=queue.c.available
                ),
            },
        )
    )


def process_one():
    current = time.time()
    tok = uuid.uuid4().hex
    with engine.begin() as conn:
        job = (
            conn.execute(
                select(queue)
                .where(queue.c.available <= current)
                .order_by(queue.c.available, queue.c.case_id)
                .limit(1)
                .with_for_update(skip_locked=True)
            )
            .mappings()
            .first()
        )
        if not job:
            return False
        cid, rev = job["case_id"], job["revision"]
        updated = conn.scalar(
            queue.update()
            .where(queue.c.case_id == cid, queue.c.available <= current)
            .values(lease=tok, available=current + 600).returning(queue.c.case_id)
        )
        if not updated:
            return False
        record = conn.execute(select(cases).where(cases.c.id == cid)).mappings().one()
        item = summary(record)
        payload = {"case": item}
        if record["photo"] and record["source"] == "live":
            data = conn.scalar(
                select(media.c.data).where(media.c.id == record["photo"])
            )
            payload["image_b64"] = base64.b64encode(data).decode()
    error = None
    try:
        if item["source"] == "seed":
            worker("/metadata", item, timeout=60)
        else:
            worker("/index", payload, timeout=240)
    except (httpx.HTTPError, ValueError) as exc:
        error = type(exc).__name__
    with engine.begin() as conn:
        guard = (queue.c.case_id == cid, queue.c.lease == tok)
        live = (
            conn.execute(select(queue).where(*guard).with_for_update())
            .mappings()
            .first()
        )
        if not live:
            return True
        if live["revision"] != rev:
            conn.execute(queue.update().where(*guard).values(lease=None, available=0))
        elif error:
            attempts = live["attempts"] + 1
            conn.execute(
                queue.update()
                .where(*guard)
                .values(
                    lease=None,
                    available=time.time() + min(60, 2 ** min(attempts, 6)),
                    attempts=attempts,
                    last_error=error,
                )
            )
        else:
            conn.execute(
                cases.update()
                .where(cases.c.id == cid, cases.c.revision == rev)
                .values(index_status="indexed")
            )
            conn.execute(queue.delete().where(*guard))
    return True


def run(stop: threading.Event):
    while not stop.is_set():
        try:
            if process_one():
                continue
        except Exception as exc:
            log.warning("Index queue iteration failed (%s)", type(exc).__name__)
        stop.wait(1)
