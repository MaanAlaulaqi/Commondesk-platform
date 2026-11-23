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

### Arabic to English model selection

The private worker can use CommonDesk's coached Arabic→English adapter, merged into the pinned MADLAD base and converted to int8. Set the Railway worker variable `MT_AR_EN_COACHED=1` and deploy the packaged worker to enable it. Set the variable to `0` and apply the deployment to return all directions to the frozen model. This manual setting has no expiry. The switch takes effect when the new worker serves traffic. The authenticated pair-specific manifest returns the active immutable revision; the API keys generated translations by that revision. Existing stored originals and reviewed translations retain their provenance.

The production deploy script requires a local authorized Hugging Face login with read access to the existing private release bucket and `huggingface_hub` supporting buckets. Set `HF_PYTHON` to that Python interpreter. The staging script issues temporary per-file read grants; BuildKit reads them through an intermediate bind mount. The final image contains the two hash-verified CPU models. Exactly one translation subprocess runs at any point. Alternating directions may incur another cold load. A missing coached artifact with the switch enabled makes Arabic→English generation unavailable. The other directions use the existing frozen release. Archived evidence without an original goes through its existing fallback.

Coached serving revision: `1e953142f1d21abdb0fc88c7ebf33d96de21be3b77c39337fa0713d5054a10b4`. Frozen production revision: `1e9bd77f519acde8a923db199e1b8ba604e90fd4ec5795b42440c847dc87445d`. The nine-incident Arabic development review accepted two coached translations, rejected six, and left one unresolved. Its separate urgency diagnostic failed. A deployment choice does not establish translation accuracy.
