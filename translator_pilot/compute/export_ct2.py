"""Merge a verified private adapter and export an int8 CT2 candidate for separate validation."""
import argparse
import hashlib
import json
import shutil
from pathlib import Path

import ctranslate2
import torch
from huggingface_hub import snapshot_download
from peft import PeftModel
from transformers import AutoModelForSeq2SeqLM, AutoTokenizer

from run import BASE, REV


def digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


def export(adapter, expected, work):
    receipt = json.loads(expected.read_text())
    for name in ("adapter_model.safetensors", "adapter_config.json"):
        if digest(adapter / name) != receipt["files"]["adapter/"+name]:
            raise ValueError(f"Adapter checksum mismatch: {name}")
    if work.exists():
        raise FileExistsError(work)
    base = snapshot_download(BASE, revision=REV, allow_patterns=["*.json","*.model","*.safetensors"])
    model = AutoModelForSeq2SeqLM.from_pretrained(base, torch_dtype=torch.bfloat16, low_cpu_mem_usage=True)
    merged = PeftModel.from_pretrained(model, adapter).merge_and_unload(safe_merge=True)
    merged_dir, output = work / "hf-merged", work / "ct2-int8"
    merged.save_pretrained(merged_dir, safe_serialization=True)
    del merged, model
    tokenizer = AutoTokenizer.from_pretrained(base)
    tokenizer.save_pretrained(merged_dir)
    ctranslate2.converters.TransformersConverter(str(merged_dir), load_as_float16=True, low_cpu_mem_usage=True).convert(
        str(output), quantization="int8")
    shutil.copyfile(Path(base) / "spiece.model", output / "spiece.model")
    report = {"base":BASE, "base_revision":REV, "adapter_sha256":receipt["files"]["adapter/adapter_model.safetensors"],
              "ctranslate2":ctranslate2.__version__, "sha256":{p.name:digest(p) for p in output.iterdir() if p.is_file()}}
    (output / "export-receipt.json").write_text(json.dumps(report,indent=2)+"\n")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("adapter", type=Path)
    parser.add_argument("receipt", type=Path)
    parser.add_argument("new_work_dir", type=Path)
    args = parser.parse_args()
    export(args.adapter, args.receipt, args.new_work_dir)
