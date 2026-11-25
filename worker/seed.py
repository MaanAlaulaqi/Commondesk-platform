"""Publish the verified Dubai v2 embeddings. Source files remain outside product git."""

import argparse
import json
from hashlib import sha256
from pathlib import Path

import numpy as np
from qdrant_client import models as q

from .encoders import PINS
from .search import COLLECTIONS, Store, point

DUBAI_2024_FILES = {
    "reports.jsonl": "47b29d6118f077ab1c1c09820b3d8ba8673840930596046a7c6e7aa9cfe18eef",
    "search/e5.npz": "aecbb29363074d05a81a0b737f7be56d2feb670421c8d530b54f2a848145aee0",
    "search/dino-photos.npz": "713f5debe0fd9bc7749c1cb9cfa15f1b91b044f5a27d34da1c80781aaf8ce5a1",
}

FILES = {
    "reports.jsonl": "f059056ff764e4f34dbda333fab7ee9cec7b33b1bbfd905328b410c65076ee6a",
    "search/e5.npz": "b19a6361e980bd3d426dd977806768b163620c6f940d20732d445eb9dd800d7c",
    "search/dino-photos.npz": "0c49cee24b9bcd8467cab2caba053dc79c7b27422c4a493d42a563bfbf8baf1d",
}


def publish(store, root):
    collection = json.loads((root / "manifest.json").read_text())["collection"]
    if collection == "DubaiV2Example":
        files, source = DUBAI_2024_FILES, "dubai2024"
    elif collection == "dubai_example_v2":
        files, source = FILES, "seed"
    else:
        raise ValueError("Unknown seed collection")
    for filename, digest in files.items():
        if sha256((root / filename).read_bytes()).hexdigest() != digest:
            raise ValueError(f"Unrecognized Dubai v2 artifact: {filename}")
    rows = [
        json.loads(line) for line in (root / "reports.jsonl").read_bytes().splitlines()
    ]
    with np.load(root / "search/e5.npz", allow_pickle=False) as cache:
        if str(cache["revision"]) != PINS["e5-small"]["revision"]:
            raise ValueError("Unexpected E5 revision")
        if source == "dubai2024" and cache["ids"].tolist() != [
            row["case_id"] for row in rows
        ]:
            raise ValueError(
                "Text vectors do not align with the published language views"
            )
        texts = cache["vectors"]
    with np.load(root / "search/dino-photos.npz", allow_pickle=False) as cache:
        if str(cache["revision"]) != PINS["dinov2-small"]["revision"]:
            raise ValueError("Unexpected DINO revision")
        photos = dict(
            zip(cache["ids"].tolist(), cache["vectors"].tolist(), strict=True)
        )
    if source == "dubai2024" and set(photos) != {row["media_id"] for row in rows}:
        raise ValueError("Expected one indexed photo for every 2024 submission")
    alias = COLLECTIONS[source]
    target = alias + "_" + files["reports.jsonl"][:12]
    aliases = {
        x.alias_name: x.collection_name for x in store.client.get_aliases().aliases
    }
    if aliases.get(alias) not in (None, target):
        raise ValueError("Existing seed alias targets a different release")
    receipt = {
        "source": source,
        "views": len(rows),
        "submissions": len({r["submission_id"] for r in rows}),
        "photos": len(photos),
        "alias": alias,
    }
    if aliases.get(alias) == target:
        if store.client.count(target, exact=True).count != len(rows):
            raise ValueError("Published seed collection is incomplete")
        # The API may have applied clerk reviews since publication. Preserve those payloads.
        return receipt
    store.ensure(source, target)
    points = []
    for i, row in enumerate(rows):
        case = {
            k: row[k]
            for k in (
                "text",
                "created_at",
                "category",
                "district",
                "status",
                "language",
            )
        }
        case.update(
            id=row["submission_id"],
            source=source,
            view_id=row["case_id"],
            urgency=row["urgency_confirmed"] or "unreviewed",
        )
        points.append(
            point(row["case_id"], case, texts[i].tolist(), photos.get(row["media_id"]))
        )
        if len(points) == 64 or i + 1 == len(rows):
            store.client.upsert(target, points, wait=True)
            points.clear()
    count = store.client.count(target, exact=True).count
    if count != len(rows):
        raise ValueError("Seed view count differs from manifest")
    if alias not in aliases:
        store.client.update_collection_aliases(
            [
                q.CreateAliasOperation(
                    create_alias=q.CreateAlias(alias_name=alias, collection_name=target)
                )
            ]
        )
    return receipt


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("seed_dir", type=Path)
    print(json.dumps(publish(Store(), parser.parse_args().seed_dir)))
