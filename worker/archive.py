"""Read-only historical evidence, optionally mounted in an authorized local environment."""

import json
import os
import re
import sqlite3
from contextlib import closing
from pathlib import Path

MANIFEST = "58050fd885d51359b1b2e61ac8a83a200f25d812b6aad8b31bac758d5fabbdc3"


def evidence(report_id, offset=None):
    if not re.fullmatch(r"[0-9a-f]{24}", report_id):
        raise ValueError("Invalid archive identifier")
    item = dict(
        id=report_id,
        report_id=report_id,
        source="archive",
        language="th",
        evidence_available=False,
        provenance="Bangkok historical archive",
        read_only=True,
    )
    if offset is not None:
        item["source_offset"] = offset
        item["detail_id"] = f"archive-{offset}-{report_id}"
    path = os.getenv("ARCHIVE_CATALOG")
    if not path:
        return item
    with closing(
        sqlite3.connect(Path(path).resolve().as_uri() + "?mode=ro", uri=True)
    ) as db:
        meta = dict(db.execute("SELECT key,value FROM metadata"))
        if (
            json.loads(meta["manifest_sha256"]) != MANIFEST
            or int(meta["reports"]) != 1434103
        ):
            raise RuntimeError("Unsupported archive catalog")
        row = db.execute(
            "SELECT source_offset,text FROM reports WHERE report_id=?", (report_id,)
        ).fetchone()
        if not row or (offset is not None and offset != row[0]):
            raise KeyError("Report missing from pinned catalog")
        return dict(
            item,
            source_offset=row[0],
            detail_id=f"archive-{row[0]}-{report_id}",
            text=row[1],
            original_text=row[1],
            evidence_available=True,
        )
