"""Select real 2024 report/photo pairs from the prepared Traffy archive."""

import argparse
import hashlib
import json
import random
import re
from bisect import bisect_left
from collections import defaultdict
from io import BytesIO
from pathlib import Path

import pyarrow.parquet as pq
from PIL import Image


def prepare(catalog, shards, places, out, limit):
    months = defaultdict(list)
    with catalog.open() as stream:
        for line in stream:
            row = json.loads(line)
            day = row["report_date"] or ""
            text = row["text"]
            if (
                day.startswith("2024-")
                and row["has_photo"]
                and re.search("[ก-๙]", text)
                and 6 <= len(text) <= 160
            ):
                months[day[:7]].append(row)
    if len(months) != 12:
        raise ValueError("Expected all twelve months of 2024")
    seen_ids, seen_images = set(), set()
    chosen = []
    for i, month in enumerate(sorted(months)):
        pool = months[month]
        random.Random(month).shuffle(pool)
        count = limit // 12 + (i < limit % 12)
        taken = 0
        for row in pool:
            if taken == count:
                break
            if row["report_id"] in seen_ids or row["image_sha256"] in seen_images:
                continue
            seen_ids.add(row["report_id"])
            seen_images.add(row["image_sha256"])
            chosen.append(row)
            taken += 1
        if taken != count:
            raise ValueError(f"Insufficient eligible cases in {month}")
    needed = {row["source_offset"]: row for row in chosen}
    out.mkdir(parents=True, exist_ok=True)
    (out / "media").mkdir(exist_ok=True)
    districts = json.loads(places.read_text())
    records = []

    offsets = sorted(needed)
    for file in sorted(shards.glob("train-*.parquet")):
        start = int(file.name.split("-")[1])
        pos = bisect_left(offsets, start)
        if pos == len(offsets):
            break
        parquet = pq.ParquetFile(file)
        if offsets[pos] >= start + parquet.metadata.num_rows:
            continue
        for r in parquet.read().to_pylist():
            row = needed.get(r["source_offset"])
            if row is None:
                continue
            photo = r["initial_photo_jpeg"]
            if (
                hashlib.sha256(b"traffy-search-v1:" + r["ticket_sha256"]).hexdigest()[
                    :24
                ]
                != row["report_id"]
                or not photo
                or hashlib.sha256(photo).hexdigest() != row["image_sha256"]
                or r["report_date"] != row["report_date"]
                or r["comment"] != row["text"]
            ):
                raise ValueError(
                    f"Report/photo provenance mismatch at {r['source_offset']}"
                )
            cid = "dv2-" + row["report_id"]
            path = "media/" + cid + ".webp"
            with Image.open(BytesIO(photo)) as image:
                image.convert("RGB").save(out / path, "WEBP", quality=88)
            rng = random.Random(cid)
            district = rng.choice(districts)
            records.append(
                dict(
                    id=cid,
                    report_id=row["report_id"],
                    text=row["text"],
                    source_offset=r["source_offset"],
                    date=r["report_date"],
                    source_image_sha256=row["image_sha256"],
                    path=path,
                    district=district["district"],
                    label=r["parent_label"],
                    lat=round(district["lat"] + rng.uniform(-0.0022, 0.0022), 5),
                    lon=round(district["lon"] + rng.uniform(-0.0022, 0.0022), 5),
                )
            )
    if len(records) != limit:
        raise ValueError("Missing source rows")
    target = out / "pairs.jsonl"
    tmp = target.with_suffix(".tmp")
    tmp.write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in records))
    tmp.replace(target)
    print(f"Verified {len(records)} report/photo pairs", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    for key in ("catalog", "shards", "places", "out"):
        parser.add_argument(key, type=Path)
    parser.add_argument("--limit", type=int, default=2500)
    args = parser.parse_args()
    prepare(**vars(args))
