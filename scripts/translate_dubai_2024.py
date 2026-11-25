"""Cache four offline NLLB translations per original complaint, resuming between batches."""

import argparse
from hashlib import sha256
import json
import re
from pathlib import Path
import sqlite3

import ctranslate2
import sentencepiece

LANGUAGES = {"en": "eng_Latn", "ar": "arb_Arab", "hi": "hin_Deva", "ur": "urd_Arab"}


TARGET_SCRIPTS = {"en": "[a-zA-Z]", "ar": "[ء-ي]", "hi": "[अ-ह]", "ur": "[ء-ے]"}


def suspicious(text, lang, wording):
    return (
        not re.search(TARGET_SCRIPTS[lang], wording)
        or len(wording) > max(100, 6 * len(text))
        or re.search(r"(.{4,48}?)(?:\1){3}", wording, re.IGNORECASE)
    )


def repair(cache, model, translator, tokenizer, lang, code):
    rows = cache.execute(
        "SELECT text, wording FROM translations WHERE lang=? AND model=?", (lang, model)
    )
    flagged = sorted(text for text, wording in rows if suspicious(text, lang, wording))
    for start in range(0, len(flagged), 8):
        batch = flagged[start : start + 8]
        tokens = [
            ["tha_Thai", *tokenizer.encode(text, out_type=str), "</s>"]
            for text in batch
        ]
        results = translator.translate_batch(
            tokens,
            target_prefix=[[code] for _ in tokens],
            beam_size=4,
            no_repeat_ngram_size=3,
            max_decoding_length=256,
        )
        entries = []
        for text, result in zip(batch, results, strict=True):
            pieces = result.hypotheses[0]
            wording = tokenizer.decode(pieces[1:]).strip()
            if pieces and pieces[0] == code and len(pieces) < 256 and wording:
                entries.append((wording, text, lang, model))
        with cache:
            cache.executemany(
                "UPDATE translations SET wording=? WHERE text=? AND lang=? AND model=?",
                entries,
            )


def translate(root, model, language=None, threads=4):
    tokenizer = sentencepiece.SentencePieceProcessor(
        model_file=str(model / "sentencepiece.bpe.model")
    )
    translator = ctranslate2.Translator(
        str(model), device="cpu", compute_type="int8", intra_threads=threads
    )
    cache = sqlite3.connect(root / "translations.sqlite", timeout=30)
    cache.execute(
        "CREATE TABLE IF NOT EXISTS translations(text, lang, model, wording, PRIMARY KEY(text, lang, model))"
    )
    revision = sha256((model / "model.bin").read_bytes()).hexdigest()
    rows = [
        json.loads(line) for line in (root / "pairs.jsonl").read_text().splitlines()
    ]
    texts = set(row["text"] for row in rows)
    for lang, code in LANGUAGES.items():
        if language and lang != language:
            continue
        completed = {
            row[0]
            for row in cache.execute(
                "SELECT text FROM translations WHERE lang=? AND model=?",
                (lang, revision),
            )
        }
        pending = sorted(texts - completed, key=lambda s: (len(s), s))
        for start in range(0, len(pending), 24):
            batch = pending[start : start + 24]
            tokens = [
                ["tha_Thai", *tokenizer.encode(text, out_type=str), "</s>"]
                for text in batch
            ]
            outputs = translator.translate_batch(
                tokens,
                target_prefix=[[code] for _ in tokens],
                beam_size=1,
                max_decoding_length=256,
            )
            entries = []
            for text, result in zip(batch, outputs, strict=True):
                pieces = result.hypotheses[0]
                if len(pieces) >= 256 or len(pieces) <= 1:
                    retry = translator.translate_batch(
                        [
                            [
                                "tha_Thai",
                                *tokenizer.encode(text, out_type=str),
                                "</s>",
                            ]
                        ],
                        target_prefix=[[code]],
                        beam_size=4,
                        no_repeat_ngram_size=3,
                        max_decoding_length=320,
                    )
                    pieces = retry[0].hypotheses[0]
                if not pieces or pieces[0] != code or len(pieces) >= 320:
                    raise ValueError(f"Incomplete translation for {lang}: {text!r}")
                wording = tokenizer.decode(pieces[1:]).strip()
                if not wording:
                    raise ValueError("Empty translation")
                entries.append((text, lang, revision, wording))
            with cache:
                cache.executemany(
                    "INSERT OR IGNORE INTO translations VALUES(?,?,?,?)", entries
                )
        repair(cache, revision, translator, tokenizer, lang, code)
    if language:
        return
    for row in rows:
        row["translations"] = dict(
            cache.execute(
                "SELECT lang, wording FROM translations WHERE text=? AND model=? ORDER BY lang",
                (row["text"], revision),
            )
        )
    path = root / "translated.jsonl"
    temp = path.with_suffix(".tmp")
    temp.write_text("".join(json.dumps(row, ensure_ascii=False) + "\n" for row in rows))
    temp.replace(path)


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    parser.add_argument("model", type=Path)
    parser.add_argument("--language", choices=LANGUAGES)
    parser.add_argument("--threads", type=int, default=4)
    translate(**vars(parser.parse_args()))
