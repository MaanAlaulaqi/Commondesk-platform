"""Pinned, CPU-only passage, query, and photograph encoders."""

from hashlib import sha256
from io import BytesIO
from pathlib import Path
import base64
import binascii
import json
import os

PINS = json.loads(Path(__file__).with_name("model-pins.json").read_text())
MODEL_DIR = Path(os.environ.get("MODEL_DIR", "/models"))


def verify(path, name):
    for filename, expected in PINS[name]["sha256"].items():
        h = sha256()
        with (path / filename).open("rb") as stream:
            for chunk in iter(lambda: stream.read(1024 * 1024), b""):
                h.update(chunk)
        if h.hexdigest() != expected:
            raise RuntimeError(f"Invalid {name} artifact {filename}")


def fetch():
    from huggingface_hub import snapshot_download

    for name, pin in PINS.items():
        path = MODEL_DIR / name
        snapshot_download(
            repo_id=pin["repo"],
            revision=pin["revision"],
            allow_patterns=list(pin["sha256"]),
            local_dir=path,
        )
        verify(path, name)


def photo(value):
    from PIL import Image, UnidentifiedImageError

    if not isinstance(value, str) or len(value) > 12 * 1024 * 1024:
        raise ValueError("Image exceeds size limit")
    try:
        with Image.open(BytesIO(base64.b64decode(value, validate=True))) as image:
            if (
                image.format not in {"JPEG", "PNG", "WEBP"}
                or image.width * image.height > 16_000_000
            ):
                raise ValueError("Unsupported photo")
            return image.convert("RGB")
    except (
        binascii.Error,
        UnidentifiedImageError,
        OSError,
        Image.DecompressionBombError,
    ) as ex:
        raise ValueError("Invalid image") from ex


class Encoders:
    def __init__(self):
        self.models = {}

    def encode(self, name, value):
        import torch
        from transformers import AutoImageProcessor, AutoModel, AutoTokenizer

        if name not in self.models:
            torch.set_num_threads(int(os.environ.get("TORCH_NUM_THREADS", "2")))
            path = MODEL_DIR / name
            verify(path, name)
            model = AutoModel.from_pretrained(path, local_files_only=True).eval()
            processor = (
                AutoTokenizer.from_pretrained(path, local_files_only=True)
                if name == "e5-small"
                else AutoImageProcessor.from_pretrained(
                    path, use_fast=False, local_files_only=True
                )
            )
            self.models[name] = model, processor
        model, processor = self.models[name]
        with torch.inference_mode():
            if name == "e5-small":
                encoded = processor(
                    [value],
                    padding=True,
                    truncation=True,
                    max_length=192,
                    return_tensors="pt",
                )
                hidden = model(**encoded).last_hidden_state
                mask = encoded.attention_mask.unsqueeze(-1)
                result = (hidden * mask).sum(1) / mask.sum(1)
            else:
                encoded = processor(images=[photo(value)], return_tensors="pt")
                result = model(**encoded).last_hidden_state[:, 0]
            return torch.nn.functional.normalize(result, dim=-1)[0].tolist()


if __name__ == "__main__":
    fetch()
