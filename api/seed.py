"""Idempotently import the authorized Dubai v2 demonstration bundle."""

import argparse
import hashlib
import json
from datetime import date, timedelta
from pathlib import Path

from sqlalchemy import func, select

from db import cases, engine, events, insert_for, media, migrate, views

DUBAI_2024_REPORTS_HASH = "47b29d6118f077ab1c1c09820b3d8ba8673840930596046a7c6e7aa9cfe18eef"
DUBAI_2024_MEDIA_HASH = "28f2b1714b9afaaf1782fc4236774caa29ef9cda8cda2c68851fa0f964383768"
REPORTS_HASH = "f059056ff764e4f34dbda333fab7ee9cec7b33b1bbfd905328b410c65076ee6a"


def seed(root: Path):
    path = root / "reports.jsonl"
    manifest = json.loads((root / "manifest.json").read_text())
    source = "seed"
    expected_count = 2348
    reports_hash = REPORTS_HASH
    if manifest["collection"] == "DubaiV2Example":
        source = "dubai2024"
        expected_count = 2500
        reports_hash = DUBAI_2024_REPORTS_HASH
        media_hash = hashlib.sha256(
            (root / "media/manifest.json").read_bytes()
        ).hexdigest()
        if media_hash != DUBAI_2024_MEDIA_HASH:
            raise ValueError("Unexpected 2024 photo manifest")
    elif manifest["collection"] != "dubai_example_v2":
        raise ValueError("Unknown seed collection")
    if hashlib.sha256(path.read_bytes()).hexdigest() != reports_hash:
        raise ValueError("Expected the verified Dubai v2 release")
    assets = json.loads((root / "media/manifest.json").read_text())["assets"]
    source_by_id = {asset["id"]: asset["source"] for asset in assets}
    rows = [json.loads(line) for line in path.read_text().splitlines()]
    migrate()
    with engine.begin() as conn:
        for asset in assets:
            if conn.scalar(select(media.c.id).where(media.c.id == asset["id"])):
                continue
            image = (root / asset["path"]).read_bytes()
            if hashlib.sha256(image).hexdigest() != asset["sha256"]:
                raise ValueError("Seed image digest mismatch")
            conn.execute(
                insert_for(media).on_conflict_do_nothing(),
                dict(
                    id=asset["id"],
                    data=image,
                    mime="image/webp",
                    alt=asset["alt"],
                    source=source,
                ),
            )
        primaries, wordings, history = [], [], []
        for r in rows:
            cid = r["submission_id"]
            wordings.append(
                dict(
                    case_id=cid,
                    language=r["language"],
                    text=r["text"],
                    view_id=r["case_id"],
                )
            )
            if not r["is_primary_view"]:
                continue
            created = date.fromisoformat(r["created_at"][:10])
            week = (created - timedelta(days=created.weekday())).isoformat()
            prop = dict(
                intent=r["intent"],
                category=r["category"],
                urgency=r["urgency_suggested"],
                evidence=r["urgency_reason_code"],
                version=manifest["collection"]
                if source == "dubai2024"
                else "dubai-example-v2",
                service_options=r["service_options"],
            )
            origin = source_by_id.get(r["media_id"], {})
            # Limit public provenance to exhibit metadata and licensed source coordinates if present.
            public_origin = {
                k: v
                for k, v in origin.items()
                if k
                in (
                    "dataset",
                    "report_id",
                    "latitude",
                    "longitude",
                    "coordinates",
                    "source_coordinates",
                    "image_version",
                )
            }
            primaries.append(
                dict(
                    id=cid,
                    incident_id=r["incident_id"],
                    source=source,
                    text=r["text"],
                    language=r["language"],
                    intent=r["intent"],
                    category=r["category"],
                    status=r["status"],
                    final_urgency=r["urgency_confirmed"],
                    suggested_urgency=r["urgency_suggested"],
                    district=r["district"],
                    latitude=r["lat"],
                    longitude=r["lon"],
                    accuracy=None,
                    location_source="simulated" if r["lat"] is not None else None,
                    day=created.isoformat(),
                    created_at=r["created_at"],
                    week_start=week,
                    photo=r["media_id"],
                    provenance=r["provenance"],
                    evidence_origin=public_origin,
                    proposal=prop,
                    service=r["selected_service"],
                    index_status="external",
                    revision=1,
                )
            )
            for e in r["events"]:
                history.append(
                    dict(
                        case_id=cid,
                        event_id=e["event_id"],
                        at=e["at"],
                        type="status",
                        status=e["status"],
                        details={"provenance": "simulated", "view_id": r["case_id"]},
                    )
                )
        for table, items in ((cases, primaries), (views, wordings), (events, history)):
            stmt = insert_for(table)
            if table is cases:
                # Backfill verified service eligibility while preserving clerk decisions and submitted evidence.
                stmt = stmt.on_conflict_do_update(
                    index_elements=[cases.c.id],
                    set_={"proposal": stmt.excluded.proposal},
                    where=cases.c.source == source,
                )
            else:
                stmt = stmt.on_conflict_do_nothing()
            for start in range(0, len(items), 100):
                conn.execute(
                    stmt,
                    items[start : start + 100],
                )
        total = conn.scalar(
            select(func.count()).select_from(cases).where(cases.c.source == source)
        )
        if total != expected_count:
            raise ValueError(f"Unexpected canonical seed count {total}")
        print(
            f"Seed verified: {total} canonical cases, {len(wordings)} language views, {len(assets)} source photos"
        )


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("directory", type=Path)
    seed(parser.parse_args().directory)
