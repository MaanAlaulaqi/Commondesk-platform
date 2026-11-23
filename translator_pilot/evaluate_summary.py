"""Build text-free, directional evidence from the private evaluation and ballots."""
import argparse
import hashlib
import json
import re
import unicodedata
from collections import Counter
from pathlib import Path


def read(path):
    return json.loads(path.read_text())


def rows(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def audit(root):
    scripts = {"en": "[A-Za-z]", "ar": "[\u0600-\u06ff]", "ur": "[\u0600-\u06ff]",
               "hi": "[\u0900-\u097f]", "th": "[\u0e00-\u0e7f]"}
    views, groups, splits = {}, {}, {}
    for group in ("train", "dev", "test"):
        sample = rows(root / (group + ".jsonl"))
        counts = Counter((r["source_lang"], r["target_lang"]) for r in sample)
        splits[group] = {"rows": len(sample), "incidents": len({r["incident_id"] for r in sample}),
                         "directions": len(counts), "rows_per_direction": sorted(set(counts.values()))}
        for row in sample:
            incident, lang, text = row["incident_id"], row["source_lang"], row["source_text"]
            if groups.setdefault(incident, group) != group:
                raise ValueError("Incident appears in multiple splits")
            if views.setdefault((incident, lang), text) != text:
                raise ValueError("Inconsistent source views")
    normalized = Counter(unicodedata.normalize("NFKC", t).strip().casefold() for t in views.values())
    lengths = [len(t) for t in views.values()]
    return {"splits": splits, "distinct_views": len(views), "min_chars": min(lengths),
            "max_chars": max(lengths), "normalized_duplicate_groups": sum(n > 1 for n in normalized.values()),
            "missing_expected_script": sum(re.search(scripts[l], t) is None for (_, l), t in views.items())}


def summarize(root):
    result = root / "results"
    judges = root / "judges"
    scores = read(judges / "tally.json")
    metrics = read(result / "metrics.json")
    receipt = read(root / "results-receipt.json")
    conditions = ("frozen", "adapter")
    source = {r["id"] for r in rows(root / "test.jsonl")}
    for arm in conditions:
        candidates = result / (arm + "_test.jsonl")
        run = rows(candidates)
        if digest(candidates) != receipt["files"][candidates.name]:
            raise ValueError("Prediction receipt mismatch")
        if len(run) != 100 or source != {row["id"] for row in run}:
            raise ValueError("Incomplete held-out set")
    mapping = {r["blind_id"]: r for r in rows(judges / "private-key.jsonl")}
    tags = {arm: Counter() for arm in conditions}
    review_digests = {}
    for reader in ("a", "b"):
        path = judges / reader / "ballot.jsonl"
        ballots = rows(path)
        if len(ballots) != 200:
            raise ValueError("Incomplete ballots")
        for ballot in ballots:
            if ballot["vote"] == "no":
                tags[mapping[ballot["blind_id"]]["model"]].update(ballot["tags"])
        review_digests[reader] = digest(path)
    for direction, data in scores.items():
        for arm in conditions:
            if sum(data[arm].values()) != 5:
                raise ValueError(f"Incomplete direction {direction}")
            data[arm]["test_chrf_pp"] = round(metrics[arm + "_test"]["chrF++"][direction], 2)
            data[arm]["dev_chrf_pp"] = round(metrics[arm + "_dev"]["chrF++"][direction], 2)
    return {
        "readers": read(judges / "readers.json"),
        "ballot_sha256": review_digests,
        "freeze_sha256": digest(root / "freeze.json"),
        "adapter_sha256": receipt["files"]["adapter/adapter_model.safetensors"],
        "data_checks": audit(root),
        "tag_counts_on_negative_votes": tags,
        "directions": scores,
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("private_run", type=Path)
    print(json.dumps(summarize(parser.parse_args().private_run), indent=2))
