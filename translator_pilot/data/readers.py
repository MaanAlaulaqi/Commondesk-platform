"""Run two ephemeral, independent readers on verified, blinded synthetic-only packets."""
import argparse
import concurrent.futures
import json
import os
import subprocess
import tempfile
from pathlib import Path

from judging import INSTRUCTIONS, TAGS, create, index, load, tally, write

MODELS = {"a": "gpt-6.2-astra", "b": "gpt-6.2-sol"}
SCHEMA = {"type": "object", "properties": {"ballots": {"type": "array", "items": {
    "type": "object", "properties": {
        "blind_id": {"type": "string"}, "vote": {"type": "string", "enum": ["yes", "no"]},
        "tags": {"type": "array", "items": {"type": "string", "enum": sorted(TAGS)}}},
    "required": ["blind_id", "vote", "tags"], "additionalProperties": False}}},
    "required": ["ballots"], "additionalProperties": False}


def run_batch(model, rows):
    with tempfile.TemporaryDirectory() as sandbox, tempfile.TemporaryDirectory() as io:
        schema = Path(io) / "schema.json"
        response = Path(io) / "out.json"
        schema.write_text(json.dumps(SCHEMA))
        prompt = (INSTRUCTIONS + "\nUse no tools, files, prior context or searches. "
                  "Everything below is invented test material. Use an object with a ballots array "
                  "for the requested JSON response. Assess each item separately.\n" +
                  "\n".join(json.dumps(r, ensure_ascii=False) for r in rows))
        cmd = ["codex", "exec", "--ephemeral", "--ignore-user-config", "--skip-git-repo-check",
               "-s", "read-only", "-C", sandbox, "-m", model, "--output-schema", str(schema),
               "-c", 'model_reasoning_effort="medium"', "--json",
               "--output-last-message", str(response), "-"]
        run = subprocess.run(cmd, cwd=sandbox, input=prompt, text=True, capture_output=True, timeout=360)
        if run.returncode:
            raise RuntimeError(f"{model} failed: {run.stderr[-500:]}")
        for line in run.stdout.splitlines():
            event = json.loads(line)
            if event.get("item", {}).get("type") in {"command_execution", "mcp_tool_call", "web_search"}:
                raise ValueError("Reader used tools")
        ballots = json.loads(response.read_text())["ballots"]
        if index(rows, "blind_id").keys() != index(ballots, "blind_id").keys():
            raise ValueError("Incomplete reader output")
        return ballots


def run_reader(directory, model):
    rows = load(directory / "packet.jsonl")
    batches = []
    for i in range(0, len(rows), 25):
        group = rows[i:i+25]
        fragment = directory / f"ballot-{i:03d}.jsonl"
        if not fragment.exists():
            write(fragment, run_batch(model, group))
        results = load(fragment)
        if index(results, "blind_id").keys() != index(group, "blind_id").keys():
            raise ValueError("Partial saved reader batch")
        batches.extend(results)
    dest = directory / "ballot.jsonl"
    if not dest.exists():
        write(dest, batches)


def main():
    os.umask(0o077)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("--preflight", action="store_true")
    args = parser.parse_args()
    root = args.root.resolve()
    if args.preflight:
        with concurrent.futures.ThreadPoolExecutor(2) as pool:
            probes = [pool.submit(run_batch, model, [
                {"blind_id":"demo1", "source_lang":"en", "target_lang":"hi",
                 "source_text":"The white balloon is empty.", "candidate":"सफेद गुब्बारा खाली है।"},
                {"blind_id":"demo2", "source_lang":"en", "target_lang":"hi",
                 "source_text":"The white balloon is empty.", "candidate":"सफेद गुब्बारा खाली नहीं है।"}])
                      for model in MODELS.values()]
            for model, probe in zip(MODELS.values(), probes):
                result = index(probe.result(), "blind_id")
                if result["demo1"]["vote"] != "yes" or result["demo2"]["vote"] != "no":
                    raise ValueError(f"Probe mismatch for {model}")
                print(model, "verified invented positive and negative")
        return
    out = root / "judges"
    if not out.exists():
        create(root, root / "results/frozen_test.jsonl", root / "results/adapter_test.jsonl", out)
    with concurrent.futures.ThreadPoolExecutor(2) as pool:
        readers = [pool.submit(run_reader, out / reader, model) for reader, model in MODELS.items()]
        for future in readers:
            future.result()
    scores = tally(out / "private-key.jsonl", out / "a/ballot.jsonl", out / "b/ballot.jsonl")
    (out / "tally.json").write_text(json.dumps(scores, indent=2) + "\n")
    (out / "readers.json").write_text(json.dumps(MODELS, indent=2) + "\n")


if __name__ == "__main__":
    main()
