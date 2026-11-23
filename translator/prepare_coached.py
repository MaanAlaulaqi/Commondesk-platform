"""Stage only validated model bytes in the private Railway build context."""

import hashlib
import json
import shutil
import sys
from pathlib import Path


def validate(manifest, directory):
    expected = json.loads(manifest.read_text())["sha256"]
    if set(p.name for p in directory.iterdir()) != set(expected):
        raise ValueError("Unexpected Arabic model file set")
    for name, digest in expected.items():
        with (directory / name).open("rb") as stream:
            if hashlib.file_digest(stream, "sha256").hexdigest() != digest:
                raise ValueError(f"Invalid Arabic model file {name}")


def stage(directory, source=None):
    manifest = Path(__file__).with_name("coached-ar-en.json")
    files = json.loads(manifest.read_text())["sha256"]
    if source:
        for name in files:
            shutil.copyfile(source / name, directory / name)
    else:
        from huggingface_hub import HfApi

        api = HfApi()
        bucket = "rocketrat/traffy-retrieval-checkpoints-v1"
        if not api.bucket_info(bucket).private:
            raise RuntimeError("Authenticated private release bucket required")
        prefix = "commondesk/mt-ar-followon/v1/serving/" + files["model.bin"]
        api.download_bucket_files(
            bucket,
            [(prefix + "/" + n, directory / n) for n in files],
            raise_on_missing_files=True,
        )
    validate(manifest, directory)


if __name__ == "__main__":
    if sys.argv[1] == "check":
        validate(Path(__file__).with_name("coached-ar-en.json"), Path(sys.argv[2]))
    else:
        stage(Path(sys.argv[1]), Path(sys.argv[2]) if len(sys.argv) > 2 else None)
