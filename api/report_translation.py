"""Translate only an authorized case original using the private, gated worker."""

import hashlib
import json
import os
import time
import uuid
from urllib.parse import urlsplit

import httpx
from db import engine, insert_for
from db import report_translations as cache
from fastapi import HTTPException
from sqlalchemy import select


def private_origin():
    origin = os.getenv("TRANSLATOR_URL", "").rstrip("/")
    if not origin:
        raise HTTPException(422, "Machine translation is disabled")
    parsed = urlsplit(origin)
    host = parsed.hostname or ""
    if (
        parsed.scheme not in {"http", "https"}
        or parsed.username
        or parsed.password
        or parsed.query
        or parsed.fragment
        or parsed.path
        or not (
            host in {"localhost", "127.0.0.1", "::1", "translator"}
            or host.endswith(".railway.internal")
        )
    ):
        raise HTTPException(503, "Private translation service is unavailable")
    return origin


def translate_report(record, target):
    original = record.get("original_text")
    source_lang = record.get("original_language")
    if (
        not original
        or not original.strip()
        or not source_lang
        or (record["source"] == "archive" and not record.get("evidence_available"))
    ):
        raise HTTPException(422, "Original report unavailable")
    if source_lang == target:
        return {"kind": "original", "text": original}
    stored = record.get("translations", {}).get(target)
    if stored and stored.strip():
        return {"kind": "stored", "text": stored}

    with httpx.Client(base_url=private_origin(), trust_env=False, timeout=45) as client:
        try:
            manifest = client.get("/manifest", timeout=4)
            manifest.raise_for_status()
            manifest = manifest.json()
            revision = manifest["model_revision"]
            directions = manifest["directions"]
            if (
                not isinstance(revision, str)
                or not revision.strip()
                or not isinstance(directions, list)
            ):
                raise ValueError("Malformed manifest")
            if f"{source_lang}:{target}" not in directions:
                raise HTTPException(
                    422, "Translation unavailable for this language pair"
                )
            scope = {
                "case_id": record.get("report_id") or record["id"],
                "source": record["source"],
                "source_digest": hashlib.sha256(original.encode()).hexdigest(),
                "source_language": source_lang,
                "target_language": target,
                "model_revision": revision,
            }
            return cached_translation(client, scope, original)
        except (httpx.HTTPError, ValueError, KeyError, TypeError):
            raise HTTPException(503, "Translation temporarily unavailable") from None


def cached_translation(client, scope, original):
    key = hashlib.sha256(json.dumps(scope, sort_keys=True).encode()).hexdigest()
    lease = uuid.uuid4().hex
    match = cache.c.cache_key == key
    deadline = time.monotonic() + 50
    while True:
        with engine.begin() as conn:
            row = conn.execute(
                select(cache.c.text, cache.c.expires_at).where(match)
            ).first()
            if row and row.text is not None:
                return {
                    "kind": "machine",
                    "text": row.text,
                    "model_revision": scope["model_revision"],
                    "cached": True,
                }
            now = time.time()
            if not row or row.expires_at <= now:
                claim = {"lease": lease, "expires_at": now + 75}
                stmt = insert_for(cache).values(cache_key=key, **scope, **claim)
                won = (
                    conn.execute(
                        stmt.on_conflict_do_update(
                            index_elements=[cache.c.cache_key],
                            set_=claim,
                            where=cache.c.text.is_(None) & (cache.c.expires_at <= now),
                        ).returning(cache.c.lease)
                    ).scalar_one_or_none()
                    == lease
                )
                if won:
                    break
        if time.monotonic() >= deadline:
            raise HTTPException(503, "Translation still in progress")
        time.sleep(0.15)

    owned = match & (cache.c.lease == lease)
    try:
        response = client.post(
            "/translate",
            json={
                "text": original,
                "source_language": scope["source_language"],
                "target_language": scope["target_language"],
            },
        )
        if response.status_code == 422:
            raise HTTPException(422, "Translation unavailable for this report")
        response.raise_for_status()
        result = response.json()
        text = result["text"]
        if (
            result["model_revision"] != scope["model_revision"]
            or not isinstance(text, str)
            or not text.strip()
        ):
            raise ValueError("Invalid generation result")
        with engine.begin() as conn:
            updated = conn.execute(
                cache.update()
                .where(owned)
                .values(text=text, lease=None, expires_at=None)
                .returning(cache.c.cache_key)
            ).scalar_one_or_none()
            if updated != key:
                raise HTTPException(503, "Translation request expired")
        return {
            "kind": "machine",
            "text": text,
            "model_revision": scope["model_revision"],
            "cached": False,
        }
    except Exception:
        with engine.begin() as conn:
            conn.execute(cache.delete().where(owned))
        raise
