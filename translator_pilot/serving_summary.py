"""Summarize aggregate measurements without copying case text or individual predictions."""
import argparse
import json
from collections import Counter
from pathlib import Path


def load(path):
    return json.loads(path.read_text())


def summarize(root):
    worker = load(root / "worker.json")
    samples = worker["warm"]
    return {
        "release": load(root / "manifest.json")["model_revision"],
        "cpu_quota": 2,
        "memory_limit_gib": 8,
        "launch_to_ready_s": load(root / "cold.json")["ready_s"],
        "first_generation": worker["first_request"],
        "successful_warm_directions": len({r["direction"] for r in samples if r["status"] == 200}),
        "warm_p50_s": worker["p50_s"],
        "warm_p95_s": worker["p95_s"],
        "longer": worker["longer"],
        "burst_statuses": dict(Counter(r["status"] for r in worker["burst"])),
        "cgroup_peak_bytes": int((root / "peak-bytes").read_text()),
        "case_api": load(root / "api.json")["samples"],
    }


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("benchmark_dir", type=Path)
    print(json.dumps(summarize(parser.parse_args().benchmark_dir), indent=2))
