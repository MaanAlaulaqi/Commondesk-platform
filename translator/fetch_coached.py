"""Fetch the signed, pinned model from a build-only bind mount."""

import hashlib
import json
import sys
from pathlib import Path
from urllib.request import urlopen


def fetch(manifest, grants, output):
    expected = json.loads(manifest.read_text())["sha256"]
    urls = json.loads(grants.read_text())
    if set(expected) != set(urls):
        raise ValueError("Incomplete Arabic release sources")
    output.mkdir(parents=True, exist_ok=True)
    for name, checksum in expected.items():
        if Path(name).name != name:
            raise ValueError("Invalid model filename")
        sha = hashlib.sha256()
        with (
            urlopen(urls[name], timeout=180) as stream,
            (output / name).open("xb") as f,
        ):
            while block := stream.read(8 << 20):
                f.write(block)
                sha.update(block)
        if sha.hexdigest() != checksum:
            raise ValueError("Arabic release digest mismatch")


if __name__ == "__main__":
    try:
        fetch(
            Path("/assets/coached-ar-en.json"),
            Path("/grants/downloads.json"),
            Path("/models/translation-ar-en"),
        )
    except Exception:
        sys.exit("Arabic model build failed: missing, expired or invalid artifact")
