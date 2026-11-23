"""Inside the pinned worker image, compare one incident across all dev directions."""
import json
from pathlib import Path

from runtime import Request, Runtime, release_revision


def rows(path):
    return [json.loads(line) for line in Path(path).read_text().splitlines()]


def main():
    dev = rows("/inputs/dev.jsonl")
    incident = dev[0]["incident_id"]
    subset = [r for r in dev if r["incident_id"] == incident]
    gpu = {r["id"]: r for r in rows("/inputs/gpu.jsonl")}
    directions = {r["source_lang"]+":"+r["target_lang"] for r in subset}
    if len(subset) != 20 or len(directions) != 20:
        raise ValueError("Expected one dev incident covering 20 directions")
    manifest = json.loads(Path("/release.json").read_text())
    revision = release_revision(manifest["sha256"])
    runtime = Runtime(Path("/model"), manifest, {"model_revision":revision, "directions":sorted(directions)})
    matched, failed = [], []
    for r in subset:
        direction = r["source_lang"]+":"+r["target_lang"]
        try:
            actual = runtime.translate(Request(source_language=r["source_lang"],target_language=r["target_lang"],
                                               text=r["source_text"]))["text"]
            if actual == gpu[r["id"]]["prediction"]:
                matched.append(direction)
        except Exception as ex:
            failed.append({"direction":direction,"error":type(ex).__name__})
    print(json.dumps({"dev_incident":incident,"n_directions":len(subset),"exact_matches":len(matched),
                      "matched_directions":matched,"failures":failed,"worker_revision":revision,
                      "gpu_decoding":"BF16 greedy max 160","cpu_decoding":"int8 beam 4 max 512"}))


if __name__ == "__main__":
    main()
