# Private report translation

The case detail page always shows the original when the case contains it. Its Report language selector first uses a stored wording. A missing wording on an eligible case goes through the case API to this worker. The response is labeled as machine-generated. Answer language belongs to Ask and can be selected independently. Hosted archive references with no original offer no translation.

The base Compose configuration does not start a translator. For an isolated evaluation, `compose.translator.yaml` adds a CPU service on a private internal network and configures the API to reach it by service name. It exposes no worker port to the public. The included control policy admits zero directions. Keep training credentials, adapters, dictionaries of report texts and judge ballots out of the image. No Hugging Face connection or access token is needed for serving. The mounted model, its manifest, and its direction policy are read-only.

## Reproduce an isolated serving check

From the platform root, prepare the API test environment at `.data/api-venv` using `api/requirements.txt`. Build the image and supply an existing CT2 directory matching the control manifest. The benchmark starts a fresh temporary container, binds only a loopback port, uses a temporary SQLite database for the API, creates invented requests and removes the container at exit.

```sh
docker build -t commondesk-mt:pilot translator
translator/bench-local.sh "$CONTROL_CT2_DIR" .data/mt-pilot/control-serving-repeat
# For a converted candidate, supply the CT2 manifest explicitly.
translator/bench-local.sh "$CANDIDATE_CT2_DIR" .data/mt-pilot/candidate-serving-repeat "$CANDIDATE_MANIFEST"
docker run --rm --network none --read-only --tmpfs /tmp \
  -v "$PWD/translator/test_runtime.py:/app/test_runtime.py:ro" \
  commondesk-mt:pilot python -m unittest -v test_runtime
```

The benchmark constructs an ephemeral all-directions policy solely for the invented test traffic. Launch-to-ready includes reading and hashing the model from local disk. First and warm requests measure HTTP response latency. Peak memory counts the container cgroup, including charged file cache. The burst test exercises the single-generation slot and two-second admission timeout. These measurements depend on hardware, page cache and report length.

## Gate and rollback

The local pilot candidate is identified by `translator_pilot/compute/ct2-export.json` and its matching closed policy `translator_pilot/evidence/candidate-policy.json`. The private converted weights are in `.data/mt-pilot/converted/ct2-int8`. Each candidate needs its own file digests and direction policy. The revision binds weight hashes, inference code and dependency pins. Check the exact served quantization and decoding settings on independent, authorized validation data before admitting a source-target direction. Removing a direction and restarting the worker revokes machine-cache hits for subsequent requests that refresh the manifest. Clearing the API's `TRANSLATOR_URL` disables the machine path entirely. Stored translations and the original continue to work in either case. Infrastructure caching or logging of request bodies should remain disabled.

A Railway staging benchmark would need a private replica, a separately approved resource limit, mounted model storage and isolated case storage. Measure startup after restart and idle, concurrent misses, cache hits, long reports, worker outages and peak memory on that service before proposing a recurring budget. Launching this optional service on production is a separate operation.
