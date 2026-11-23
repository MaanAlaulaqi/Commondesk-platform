"""Single-attempt GPU pilot. Reads only a checksummed synthetic fixture bundle."""
import argparse
import hashlib
import json
import os
import random
import resource
import time
from collections import defaultdict
from pathlib import Path

import torch
from peft import LoraConfig, TaskType, get_peft_model
from sacrebleu.metrics import CHRF
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer, set_seed

BASE = "google/madlad400-3b-mt"
REV = "fa184c675da0b5c9e1c8694fccd4e12e2d422094"
SEED = 2147
BATCH = 8


def read_rows(folder):
    receipt = json.loads((folder / "freeze.json").read_text())
    splits = {}
    seen = set()
    for name in ["train", "dev", "test"]:
        path = folder / f"{name}.jsonl"
        expected = receipt["files"][path.name]
        if isinstance(expected, dict):
            expected = expected["sha256"]
        if hashlib.sha256(path.read_bytes()).hexdigest() != expected:
            raise ValueError(f"Freeze mismatch: {name}")
        rows = [json.loads(line) for line in path.read_text().splitlines()]
        incidents = {r["incident_id"] for r in rows}
        if seen & incidents:
            raise ValueError("Incident split overlap")
        seen |= incidents
        directions = {(r["source_lang"], r["target_lang"]) for r in rows}
        languages = {"th", "en", "ar", "hi", "ur"}
        if directions != {(s,t) for s in languages for t in languages if s != t}:
            raise ValueError("Missing direction")
        splits[name] = rows
    return splits


def encode(tokenizer, rows):
    texts = [f"<2{r['target_lang']}> {r['source_text']}" for r in rows]
    encoded = tokenizer(texts, padding=True, return_tensors="pt")
    if encoded.input_ids.shape[1] > 384:
        raise ValueError("Source exceeds pilot input limit")
    return encoded.to("cuda")


def decode(model, tokenizer, rows, path):
    model.eval()
    predictions = []
    timings = []
    chrf = CHRF(word_order=2)
    by_direction = defaultdict(list)
    with torch.inference_mode():
        for start in range(0, len(rows), BATCH):
            batch = rows[start:start+BATCH]
            enc = encode(tokenizer, batch)
            torch.cuda.synchronize()
            tic = time.monotonic()
            generated = model.generate(**enc, num_beams=1, do_sample=False, max_new_tokens=160)
            torch.cuda.synchronize()
            timings.append(time.monotonic() - tic)
            for r, token_ids, prediction in zip(batch, generated, tokenizer.batch_decode(generated, skip_special_tokens=True)):
                result = {k: r[k] for k in ("id", "incident_id", "source_lang", "target_lang")}
                result.update(prediction=prediction, complete=bool((token_ids == tokenizer.eos_token_id).any()))
                predictions.append(result)
                by_direction[r["source_lang"]+"-"+r["target_lang"]].append((prediction, r["target_text"]))
    path.write_text("".join(json.dumps(r, ensure_ascii=False)+"\n" for r in predictions))
    return {"batch_seconds": timings, "generated":len(predictions), "without_eos":sum(not r["complete"] for r in predictions),
            "chrF++":{k:chrf.corpus_score([p for p,_ in v], [[t for _,t in v]]).score for k,v in by_direction.items()}}


def main(data, out):
    splits = read_rows(data)
    out.mkdir(parents=True, exist_ok=False)
    set_seed(SEED)
    if not torch.cuda.is_available() or not torch.cuda.is_bf16_supported():
        raise RuntimeError("A BF16 GPU is required")
    tic = time.monotonic()
    model_path = os.environ.get("MADLAD_MODEL_PATH", BASE)
    tokenizer = AutoTokenizer.from_pretrained(model_path, revision=REV)
    model = AutoModelForSeq2SeqLM.from_pretrained(model_path, revision=REV, torch_dtype=torch.bfloat16,
                                                   low_cpu_mem_usage=True).to("cuda")
    metrics = {"model":BASE, "revision":REV, "gpu":torch.cuda.get_device_name(), "seed":SEED,
               "torch":torch.__version__, "load_seconds":time.monotonic()-tic}
    # Fixed update count and hyperparameters. No held-out result influences fitting.
    for split in ("dev","test"):
        metrics["frozen_"+split] = decode(model, tokenizer, splits[split], out / f"frozen_{split}.jsonl")
    model = get_peft_model(model, LoraConfig(task_type=TaskType.SEQ_2_SEQ_LM, r=8, lora_alpha=16,
                                             lora_dropout=0.05, target_modules=["q","v"]))
    metrics["trainable_parameters"], metrics["total_parameters"] = model.get_nb_trainable_parameters()
    model.train()
    optimizer = torch.optim.AdamW([p for p in model.parameters() if p.requires_grad], lr=5e-5)
    train = list(splits["train"])
    random.Random(SEED).shuffle(train)
    losses = []
    for start in range(0, len(train), BATCH):
        rows = train[start:start+BATCH]
        labels = tokenizer([r["target_text"] for r in rows], return_tensors="pt", padding=True)
        ids = labels.input_ids.masked_fill(labels.attention_mask == 0, -100).to("cuda")
        optimizer.zero_grad(set_to_none=True)
        loss = model(**encode(tokenizer, rows), labels=ids, use_cache=False).loss
        if not torch.isfinite(loss):
            raise RuntimeError("Nonfinite training loss")
        loss.backward()
        torch.nn.utils.clip_grad_norm_(model.parameters(), 1.0)
        optimizer.step()
        losses.append(float(loss.detach()))
    metrics["train_losses"] = losses
    model.save_pretrained(out / "adapter")
    for split in ("dev","test"):
        metrics["adapter_"+split] = decode(model, tokenizer, splits[split], out / f"adapter_{split}.jsonl")
    metrics.update(elapsed_s=time.monotonic()-tic, max_allocated_gpu_bytes=torch.cuda.max_memory_allocated(),
                   max_rss_kib=resource.getrusage(resource.RUSAGE_SELF).ru_maxrss)
    (out / "metrics.json").write_text(json.dumps(metrics, indent=2)+"\n")
    print(f"Completed {len(losses)} optimizer updates; wrote both arms", flush=True)


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("data", type=Path)
    parser.add_argument("out", type=Path)
    args = parser.parse_args()
    main(args.data, args.out)
