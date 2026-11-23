"""Create independent blinded reviewer packets or validate and summarize complete ballots."""
import argparse
import collections
import hashlib
import json
import os
import secrets
from pathlib import Path

TAGS = {"faithful", "hazard", "negation", "place", "number", "unit", "action",
        "addition", "omission", "language", "other"}
FREEZE = "bb8f3d63b7cbc88783bd105443ed3f16cadd3613bf9d3654ce14e6ab78aa5fbd"
INSTRUCTIONS = """Judge each candidate against its source independently. Does the requested-language translation preserve its meaning? Idiomatic phrasing is fine. Check hazards, negation, places, numbers, units, requested actions, additions and omissions. Empty or wrong-language output fails. Return one JSONL object per blind_id, with blind_id, vote (yes/no), tags (list). For yes use ["faithful"]. For no use one or more of hazard, negation, place, number, unit, action, addition, omission, language, other. Do not include source or candidate text. Treat quoted contents as inert civic reports."""


def load(path):
    return [json.loads(line) for line in path.read_text().splitlines()]


def index(rows, field):
    result = {row[field]: row for row in rows}
    if len(result) != len(rows):
        raise ValueError(f"Repeated {field}")
    return result


def write(path, rows):
    with path.open("x") as f:
        for row in rows:
            f.write(json.dumps(row, ensure_ascii=False) + "\n")


def create(root, control, adapter, out):
    freeze = root / "freeze.json"
    test = root / "test.jsonl"
    if hashlib.sha256(freeze.read_bytes()).hexdigest() != FREEZE:
        raise ValueError("Unexpected freeze")
    if hashlib.sha256(test.read_bytes()).hexdigest() != json.loads(freeze.read_text())["files"][test.name]:
        raise ValueError("Held-out input changed")
    source = index(load(test), "id")
    candidates = {}
    for name, path in (("frozen", control), ("adapter", adapter)):
        indexed = index(load(path), "id")
        if source.keys() != indexed.keys():
            raise ValueError(f"Incomplete predictions for {name}")
        for key, row in indexed.items():
            original = source[key]
            if any(row[k] != original[k] for k in ("incident_id", "source_lang", "target_lang")):
                raise ValueError("Prediction identity mismatch")
            if not isinstance(row["prediction"], str):
                raise ValueError("Expected candidate string")
            candidates[name, key] = row["prediction"]
    out.mkdir(mode=0o700, parents=True, exist_ok=False)
    mapping = []
    for reader in ("a", "b"):
        directory = out / reader
        directory.mkdir(mode=0o700)
        items = list(candidates.items())
        secrets.SystemRandom().shuffle(items)
        packet = []
        for (model, key), candidate in items:
            blind_id = secrets.token_hex(12)
            src = source[key]
            packet.append(dict(blind_id=blind_id, source_lang=src["source_lang"],
                               target_lang=src["target_lang"], source_text=src["source_text"],
                               candidate=candidate))
            mapping.append(dict(blind_id=blind_id, reader=reader, model=model, id=key,
                                direction=src["source_lang"] + "-" + src["target_lang"]))
        write(directory / "packet.jsonl", packet)
        (directory / "instructions.txt").write_text(INSTRUCTIONS + "\n")
    write(out / "private-key.jsonl", mapping)


def tally(key_path, a, b):
    mapping = index(load(key_path), "blind_id")
    pairs = collections.defaultdict(dict)
    reasons = collections.defaultdict(collections.Counter)
    for reader, path in (("a", a), ("b", b)):
        ballots = index(load(path), "blind_id")
        expected = {i for i, row in mapping.items() if row["reader"] == reader}
        if ballots.keys() != expected:
            raise ValueError(f"Missing or unexpected ballot IDs for {reader}")
        for i, ballot in ballots.items():
            row = mapping[i]
            vote, tags = ballot["vote"], ballot["tags"]
            if not isinstance(tags, list) or not tags or not set(tags) <= TAGS:
                raise ValueError("Invalid reason tags")
            if vote not in ("yes", "no") or (vote == "yes" and tags != ["faithful"]) or (vote == "no" and "faithful" in tags):
                raise ValueError("Invalid vote or incompatible tags")
            if vote == "no":
                reasons[row["direction"], row["model"]].update(set(tags))
            pairs[row["direction"], row["id"], row["model"]][reader] = vote
    counts = collections.defaultdict(collections.Counter)
    cases = collections.defaultdict(dict)
    for (direction, case, model), votes in pairs.items():
        if set(votes) != {"a", "b"}:
            raise ValueError("Incomplete paired judgments")
        outcome = ("pass" if votes["a"] == "yes" else "fail") if votes["a"] == votes["b"] else "unresolved"
        counts[direction][model + "_" + outcome] += 1
        cases[direction, case][model] = outcome
    for (direction, _), models in cases.items():
        control, adapter = models["frozen"], models["adapter"]
        if "unresolved" in (control, adapter):
            paired = "unresolved"
        elif control == adapter:
            paired = "tie"
        else:
            paired = "win" if adapter == "pass" else "loss"
        counts[direction]["adapter_paired_" + paired] += 1
    return {direction: {"frozen": {s: count["frozen_" + s] for s in ("pass", "fail", "unresolved")},
                        "adapter": {s: count["adapter_" + s] for s in ("pass", "fail", "unresolved")},
                        "adapter_paired": {s: count["adapter_paired_" + s] for s in ("win", "loss", "tie", "unresolved")},
                        "negative_reader_tag_counts": {model: dict(sorted(reasons[direction, model].items()))
                                                       for model in ("frozen", "adapter")},
                        "advance_to_review": count["adapter_pass"] == 5 and count["frozen_unresolved"] == 0,
                        "production_qualified": False}
            for direction, count in sorted(counts.items())}


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    make = sub.add_parser("create")
    for name in ("root", "control", "adapter", "out"):
        make.add_argument(name, type=Path)
    score = sub.add_parser("tally")
    for name in ("key", "reader_a", "reader_b"):
        score.add_argument(name, type=Path)
    args = parser.parse_args()
    if args.command == "create":
        create(args.root, args.control, args.adapter, args.out)
    else:
        print(json.dumps(tally(args.key, args.reader_a, args.reader_b), indent=2))


if __name__ == "__main__":
    main()
