"""Build the DubaiV2Example vectors using the same pinned encoders as the live worker."""

import argparse
from hashlib import sha256
import json
from pathlib import Path
import sys

import numpy as np
import torch


def build(root, kit, channel):
    sys.path.insert(0, str(kit / "engine"))
    from train_traffy_retrieval import Encoder

    folder = root / "search"
    folder.mkdir(exist_ok=True)
    torch.set_num_threads(3)
    if channel == "photo":
        rows = [
            json.loads(line) for line in (root / "pairs.jsonl").read_text().splitlines()
        ]
        values = [root / row["path"] for row in rows]
        ids = [row["id"] for row in rows]
        model, filename = "dinov2-small", "dino-photos"
    else:
        rows = [
            json.loads(line)
            for line in (root / "reports.jsonl").read_text().splitlines()
        ]
        values = ["passage: " + row["text"] for row in rows]
        ids = [row["case_id"] for row in rows]
        model, filename = "e5-small", "e5"
    encoder = Encoder(kit / "models", model, "cpu")
    if channel == "text":
        # Batch similar lengths to reduce padding, then restore canonical view order.
        passages = sorted(set(values), key=lambda text: (len(text), text))
        position = {text: i for i, text in enumerate(passages)}
        encoded = np.concatenate(list(encoder.encode(passages, batch_size=32)))
        vectors = encoded[[position[text] for text in values]]
    else:
        vectors = np.concatenate(list(encoder.encode(values, batch_size=16)))
    pin = json.loads((kit / "models" / model / "provenance.json").read_text())
    if vectors.shape != (len(ids), 384) or not np.allclose(
        np.linalg.norm(vectors, axis=1), 1, atol=1e-5
    ):
        raise ValueError("Invalid embeddings")
    target = folder / (filename + ".npz")
    with target.with_suffix(".tmp").open("wb") as stream:
        np.savez_compressed(stream, vectors=vectors, ids=ids, revision=pin["revision"])
    target.with_suffix(".tmp").replace(target)
    print(filename, len(ids), sha256(target.read_bytes()).hexdigest(), flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("kit", type=Path)
    parser.add_argument("channel", choices=("photo", "text"))
    build(**vars(parser.parse_args()))
