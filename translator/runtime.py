"""CPU translation of case originals using a locally mounted CTranslate2 release."""
import hashlib
import json
import os
from pathlib import Path
from threading import BoundedSemaphore
from typing import Literal

import ctranslate2
import sentencepiece
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, ConfigDict, Field

LANG = Literal["en", "ar", "th", "hi", "ur"]
LANGUAGES = {"en", "ar", "th", "hi", "ur"}


def release_revision(files):
    """Bind cache and gate records to the exact weights, runtime and dependencies."""
    here = Path(__file__).resolve().parent
    identity = {"weights": files, "runtime": file_digest(here / "runtime.py"),
                "dependencies": file_digest(here / "requirements.txt")}
    return hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()


class Request(BaseModel):
    model_config = ConfigDict(extra="forbid")
    text: str = Field(min_length=1, max_length=8000)
    source_language: LANG
    target_language: LANG


def file_digest(path):
    with path.open("rb") as handle:
        return hashlib.file_digest(handle, "sha256").hexdigest()


class Runtime:
    def __init__(self, model_dir, manifest, policy):
        files = manifest["sha256"]
        if not {"model.bin", "config.json", "spiece.model", "shared_vocabulary.json"} <= files.keys():
            raise ValueError("Incomplete CT2 release")
        for name, digest in files.items():
            if Path(name).name != name or file_digest(model_dir / name) != digest:
                raise ValueError("Invalid translation artifact")
        self.revision = release_revision(files)
        if policy.get("model_revision") != self.revision:
            raise ValueError("Direction policy belongs to a different model")
        self.directions = frozenset(policy["directions"])
        if not self.directions <= {s+":"+t for s in LANGUAGES for t in LANGUAGES if s != t}:
            raise ValueError("Unknown language direction")
        self.tokenizer = sentencepiece.SentencePieceProcessor(model_file=str(model_dir/"spiece.model"))
        self.engine = ctranslate2.Translator(str(model_dir), device="cpu", compute_type="int8",
                                             intra_threads=int(os.getenv("MT_THREADS", "2")), inter_threads=1)
        self.slot = BoundedSemaphore(1)

    def translate(self, body):
        if body.source_language+":"+body.target_language not in self.directions:
            raise HTTPException(422, "Translation is unavailable for this language pair")
        if not body.text.strip():
            raise HTTPException(422, "The original report is empty")
        pieces = self.tokenizer.encode(f"<2{body.target_language}> " + body.text, out_type=str) + ["</s>"]
        if len(pieces) > 512:
            raise HTTPException(422, "Report exceeds the verified translation length")
        if not self.slot.acquire(timeout=2):
            raise HTTPException(429, "Translation worker is busy")
        try:
            result = self.engine.translate_batch([pieces], beam_size=4, max_input_length=512,
                                                  max_decoding_length=512, return_end_token=True)[0]
        finally:
            self.slot.release()
        tokens = result.hypotheses[0]
        if not tokens or tokens[-1] != "</s>":
            raise HTTPException(422, "Incomplete translation")
        output = self.tokenizer.decode_pieces(tokens[:-1]).strip()
        if not output:
            raise HTTPException(422, "Empty translation")
        return {"text": output, "model_revision": self.revision}


def create_app():
    model = Path(os.environ["MT_MODEL_DIR"])
    runtime = Runtime(model, json.loads(Path(os.environ["MT_MODEL_MANIFEST"]).read_text()),
                      json.loads(Path(os.environ["MT_DIRECTION_POLICY"]).read_text()))
    app = FastAPI(docs_url=None, redoc_url=None, openapi_url=None)

    @app.get("/manifest")
    @app.get("/readyz")
    def manifest():
        return {"model_revision": runtime.revision, "directions": sorted(runtime.directions)}

    @app.post("/translate")
    def translate(body: Request):
        return runtime.translate(body)
    return app
