"""Submit the fixed, private, single-attempt pilot. No token is copied into the job."""
import hashlib
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from shutil import copyfile

from huggingface_hub import HfApi, Volume

NAME = "commondesk-mt-synthetic-v1"
REPO = "rocketrat/traffy-retrieval-training-v1"
BUCKET = "rocketrat/traffy-retrieval-checkpoints-v1"
PREFIX = "commondesk/mt-pilot-v1"
IMAGE = "pytorch/pytorch@sha256:417bd75df6365104c283ea4c1651fb3530d9eb5a4c2fafa51943cff2a94e6385"
MODEL = "google/madlad400-3b-mt"
REVISION = "fa184c675da0b5c9e1c8694fccd4e12e2d422094"
MINUTES = 45


def main():
    api = HfApi()
    files = Path(__file__).resolve().parent
    root = files.parents[1]
    data = root / ".data/mt-pilot"
    frozen_bytes = (data / "freeze.json").read_bytes()
    if hashlib.sha256(frozen_bytes).hexdigest() != "bb8f3d63b7cbc88783bd105443ed3f16cadd3613bf9d3654ce14e6ab78aa5fbd":
        raise ValueError("Expected signed synthetic pilot manifest")
    freeze = json.loads(frozen_bytes)
    if not api.dataset_info(REPO).private or not api.bucket_info(BUCKET).private:
        raise RuntimeError("Private staging and output storage are required")
    if any(j.labels.get("name") == NAME for j in api.list_jobs()):
        raise RuntimeError("Pilot already submitted")
    rate = next(h.unit_cost_usd for h in api.list_jobs_hardware() if h.name == "a100-large")
    if MINUTES * rate > 2:
        raise RuntimeError("Outside pilot compute cap")
    with TemporaryDirectory() as tmp:
        stage = Path(tmp)
        for name in ("train.jsonl","dev.jsonl","test.jsonl"):
            value = freeze["files"][name]
            digest = value if isinstance(value, str) else value["sha256"]
            if hashlib.sha256((data / name).read_bytes()).hexdigest() != digest:
                raise ValueError(f"Freeze mismatch: {name}")
            copyfile(data / name, stage / name)
        copyfile(data / "freeze.json", stage / "freeze.json")
        for name in ("requirements.txt","run.py"):
            copyfile(files / name, stage / name)
        rev = api.upload_folder(repo_id=REPO, repo_type="dataset", folder_path=stage,
                                path_in_repo=PREFIX, commit_message="Stage frozen synthetic translation pilot").oid
    job = api.run_job(name=NAME, image=IMAGE, flavor="a100-large", timeout=MINUTES*60, attempts=1,
                      labels={"project":"commondesk","task":"translation-pilot"}, env={"MADLAD_MODEL_PATH":"/weights"},
                      volumes=[Volume(type="dataset", source=REPO, revision=rev, path=PREFIX,
                                      mount_path="/stage", read_only=True),
                               Volume(type="model", source=MODEL, revision=REVISION,
                                      mount_path="/weights", read_only=True),
                               Volume(type="bucket", source=BUCKET, mount_path="/artifacts", read_only=False)],
                      command=["bash","-ec","python -m pip install -q --disable-pip-version-check -r /stage/requirements.txt && "
                               "mkdir -p /artifacts/commondesk && HF_HUB_OFFLINE=1 python -u /stage/run.py /stage /tmp/pilot && "
                               "cp -r /tmp/pilot /artifacts/commondesk/mt-pilot-v1"])
    print(json.dumps({"id":job.id,"name":NAME,"private_stage_revision":rev,"base_revision":REVISION,
                      "image":IMAGE,"rate_usd_min":rate,"timeout_minutes":MINUTES,"maximum_compute_usd":MINUTES*rate}))


if __name__ == "__main__":
    main()
