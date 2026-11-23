#!/usr/bin/env bash
# Run from the repository root, using existing weights and an isolated local image.
set -euo pipefail
model=$(realpath "${1:?path to the verified CT2 release}")
out=$(realpath -m "${2:?new output directory below .data}")
manifest=$(realpath "${3:-translator/control.json}")
case "$out" in "$(pwd)/.data/"*) ;; *) exit 2 ;; esac
mkdir -m 700 "$out"
python - "$out" "$manifest" <<'PY'
import hashlib, itertools, json, pathlib, sys, time
p = pathlib.Path(sys.argv[1])
def digest(path):
    return hashlib.sha256(pathlib.Path(path).read_bytes()).hexdigest()
files = json.loads(pathlib.Path(sys.argv[2]).read_text())["sha256"]
identity = {"weights": files, "runtime": digest("translator/runtime.py"),
            "dependencies": digest("translator/requirements.txt")}
policy = {"model_revision": hashlib.sha256(json.dumps(identity, sort_keys=True).encode()).hexdigest()}
policy["directions"] = [a + ":" + b for a, b in itertools.permutations(["th","en","ar","hi","ur"], 2)]
(p/"temporary-policy.json").write_text(json.dumps(policy))
(p/"start-ns").write_text(str(time.monotonic_ns()))
PY
container=$(docker run -d --read-only --cpus=2 --memory=8g --cap-drop=ALL \
  --security-opt=no-new-privileges -p 127.0.0.1::8012 \
  -v "$model:/model:ro" -v "$manifest:/release.json:ro" \
  -v "$out/temporary-policy.json:/policy.json:ro" \
  -e MT_MODEL_DIR=/model -e MT_MODEL_MANIFEST=/release.json -e MT_DIRECTION_POLICY=/policy.json \
  commondesk-mt:pilot)
trap 'docker rm -f "$container" >/dev/null' EXIT
port=$(docker port "$container" 8012/tcp | cut -d: -f2)
for i in {1..120}; do
  if curl -fsS "http://127.0.0.1:$port/readyz" -o "$out/manifest.json" 2>/dev/null; then break; fi
  sleep 1
done
test -s "$out/manifest.json"
python - "$out" <<'PY'
import json,pathlib,sys,time
p = pathlib.Path(sys.argv[1])
(p/"cold.json").write_text(json.dumps({"ready_s":(time.monotonic_ns()-int((p/"start-ns").read_text()))/1e9}))
PY
python translator/benchmark.py "$port" > "$out/worker.json"
.data/api-venv/bin/python api/bench_report_translation.py "$port" --output "$out/api.json" > /dev/null
docker exec "$container" cat /sys/fs/cgroup/memory.peak > "$out/peak-bytes"
