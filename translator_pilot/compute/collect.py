"""Collect completed private pilot results and hash every file, including weights."""
import hashlib
import json
from pathlib import Path

from huggingface_hub import HfApi

from dispatch import BUCKET, PREFIX, NAME


def collect(root):
    api = HfApi()
    receipt = json.loads((root / "provider-job.json").read_text())
    job = api.inspect_job(job_id=receipt["id"])
    if job.labels.get("name") != NAME or job.status.stage != "COMPLETED" or not api.bucket_info(BUCKET).private:
        raise RuntimeError(f"Private completed pilot required ({job.status.stage})")
    out = root / "results"
    files = []
    for obj in api.list_bucket_tree(BUCKET, prefix=PREFIX, recursive=True):
        if hasattr(obj, "size"):
            rel = Path(obj.path).relative_to(PREFIX)
            path = out / rel
            path.parent.mkdir(parents=True, exist_ok=True)
            files.append((obj.path, path))
    required = {"metrics.json","adapter/adapter_config.json","adapter/adapter_model.safetensors",
                "frozen_dev.jsonl","frozen_test.jsonl","adapter_dev.jsonl","adapter_test.jsonl"}
    if not required.issubset({str(path.relative_to(out)) for _, path in files}):
        raise ValueError("Incomplete remote artifact set")
    api.download_bucket_files(BUCKET, files, raise_on_missing_files=True)
    hashes = {}
    for _, path in files:
        with path.open("rb") as f:
            hashes[str(path.relative_to(out))] = hashlib.file_digest(f, "sha256").hexdigest()
    receipt.update(files=hashes, stage=job.status.stage, scheduled_secs=job.durations.scheduling_secs,
                   running_secs=job.durations.running_secs, total_secs=job.durations.total_secs,
                   finished_at=job.finished_at.isoformat(), started_at=job.started_at.isoformat())
    (root / "results-receipt.json").write_text(json.dumps(receipt,indent=2)+"\n")


if __name__ == "__main__":
    collect(Path(__file__).resolve().parents[2] / ".data/mt-pilot")
