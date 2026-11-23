"""Fetch pinned public weights at build time. No case data or tokens are used."""
import hashlib
import json
import shutil
from pathlib import Path
from urllib.request import urlopen


def fetch(manifest_path, directory):
    manifest = json.loads(manifest_path.read_text())
    directory.mkdir(parents=True, exist_ok=True)
    for name, expected in manifest["sha256"].items():
        if Path(name).name != name:
            raise ValueError("Invalid weight filename")
        url = f"https://huggingface.co/{manifest['repo']}/resolve/{manifest['revision']}/{name}?download=true"
        with urlopen(url, timeout=240) as source, (directory / name).open("wb") as dest:
            shutil.copyfileobj(source, dest)
        with (directory / name).open("rb") as artifact:
            if hashlib.file_digest(artifact, "sha256").hexdigest() != expected:
                raise ValueError(f"Invalid digest for {name}")


if __name__ == "__main__":
    fetch(Path(__file__).with_name("control.json"), Path("/models/translation"))
