"""Expand private incident views into deterministic directional files, then attest the freeze."""
import argparse
import hashlib
import itertools
import json
import subprocess
import tempfile
from collections import Counter
from pathlib import Path

LANGUAGES = ("en", "th", "ar", "hi", "ur")
COUNTS = {"train": 25, "dev": 5, "test": 5}


def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("root", type=Path)
    root = parser.parse_args().root.resolve()
    if (root / "freeze.json").exists():
        raise SystemExit("A freeze exists. Use a fresh directory for a new version.")
    source = root / "incidents.psv"
    protocol = Path(__file__).with_name("protocol.md")
    cases = {}
    seen = set()
    counts = Counter()
    for line in source.read_text().splitlines():
        case, split, *views = line.split("|")
        if (case in cases or split not in COUNTS or len(views) != 5
                or any(not text.strip() or text in seen for text in views)):
            raise ValueError(f"Invalid or repeated incident/view: {case}")
        cases[case] = split, dict(zip(LANGUAGES, views))
        counts[split] += 1
        seen.update(views)
    if counts != COUNTS:
        raise ValueError(counts)
    files = {"incidents.psv": sha(source)}
    for split in COUNTS:
        path = root / f"{split}.jsonl"
        with path.open("x") as out:
            for case, (group, views) in cases.items():
                if group != split:
                    continue
                for a, b in itertools.permutations(LANGUAGES, 2):
                    row = dict(id=f"{case}.{a}-{b}", incident_id=case, source_lang=a,
                               target_lang=b, source_text=views[a], target_text=views[b])
                    out.write(json.dumps(row, ensure_ascii=False) + "\n")
        files[path.name] = sha(path)
    manifest = dict(version=1, source="original_synthetic", incidents=dict(counts),
                    files=files, protocol_sha256=sha(protocol))
    receipt = root / "freeze.json"
    receipt.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n")
    with tempfile.TemporaryDirectory() as tmp:
        key = Path(tmp) / "run-local"
        subprocess.run(["ssh-keygen", "-q", "-t", "ed25519", "-N", "", "-C",
                        "synthetic-pilot-freeze", "-f", str(key)], check=True)
        (root / "allowed_signers").write_text("pilot " + key.with_suffix(".pub").read_text())
        subprocess.run(["ssh-keygen", "-Y", "sign", "-f", str(key), "-n",
                        "commondesk-mt", str(receipt)], check=True)
    with receipt.open() as stream:
        subprocess.run(["ssh-keygen", "-Y", "verify", "-f", str(root / "allowed_signers"),
                        "-I", "pilot", "-n", "commondesk-mt", "-s", str(receipt) + ".sig"],
                       stdin=stream, check=True)
    print(sha(receipt))


if __name__ == "__main__":
    main()
