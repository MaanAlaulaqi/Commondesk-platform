# Private report translation

The case detail page always shows the original when the case contains it. Its Report language selector first uses a stored wording. A missing wording on an eligible case goes through the case API to this worker. The response is labeled as machine-generated. Answer language belongs to Ask and can be selected independently. Hosted archive references with no original offer no translation.

The base Compose configuration does not start a translator. For an isolated evaluation, `compose.translator.yaml` adds a CPU service on a private internal network and configures the API to reach it by service name. It exposes no worker port to the public. The included control policy admits zero directions. Keep training credentials, adapters, dictionaries of report texts and judge ballots out of the image. No Hugging Face connection or access token is needed for serving. The mounted model, its manifest, and its direction policy are read-only.

## Local verification

The worker regression uses synthetic test inputs in an isolated container. Run it from the repository root.

```sh
docker build -t commondesk-mt:test translator
docker run --rm --network none --read-only --tmpfs /tmp \
  -v "$PWD/translator/test_runtime.py:/app/test_runtime.py:ro" \
  commondesk-mt:test python -m unittest -v test_runtime
```

The internal research branch `translator-pilot-20261123` holds the training, evaluation, latency benchmarks and pilot evidence. No direction qualified for production.

## Gate and rollback

Each candidate needs its own file digests and direction policy. The revision binds weight hashes, inference code and dependency pins. Check the exact served quantization and decoding settings on independent, authorized validation data before admitting a source-target direction. Removing a direction and restarting the worker revokes machine-cache hits for subsequent requests that refresh the manifest. Clearing the API's `TRANSLATOR_URL` disables the machine path entirely. Stored translations and the original continue to work in either case. Infrastructure caching or logging of request bodies should remain disabled.

A Railway staging benchmark would need a private replica, a separately approved resource limit, mounted model storage and isolated case storage. Measure startup after restart and idle, concurrent misses, cache hits, long reports, worker outages and peak memory on that service before proposing a recurring budget. Launching this optional service on production is a separate operation.
