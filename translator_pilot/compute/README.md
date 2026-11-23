# Internal synthetic translation pilot

One HF Jobs A100 80 GB ran both the frozen google/madlad400-3b-mt control and a PEFT LoRA adapter. The model, tokenizer, training code and data revisions are bound in the run receipt. The private staging commit contains only the synthetic train, dev and test JSONL, the freeze manifest, the runner and its package pins. The job mounted the immutable model and staging data read-only. Its output uses the project's existing private artifact bucket.

The runner uses all 500 training rows once, batch 8, seed 2147, AdamW at 5e-5, gradient norm clipping at 1, BF16 compute, rank 8 and alpha 16 with 0.05 dropout on T5 attention q and v. Both conditions use greedy decoding with 160 new tokens. All 100 dev and all 100 held-out rows are retained in each arm, including truncated and empty candidates. Five incident families per held-out direction limit inference. chrF++ is a descriptive reference-overlap measure. See the separate signed data protocol and blinded judgments for fidelity gates.

## Reproduction

The companion local notebook is `colab-files/18_commondesk_madlad_adapter.ipynb` in the research workspace. It downloads the pinned private stage and runs the same code on a BF16 GPU. It requires a read-only token for that dataset and an authorized runtime. The original image used PyTorch 2.8.0 with CUDA 12.8. The original job timeout was 45 minutes, attempts 1. The name guard in `dispatch.py` rejects duplicate submissions on the original account.

For existing completed jobs, run `collect.py` under huggingface_hub 2.4.0. It writes checksummed private results beneath `.data/mt-pilot`. Each arm and split has a JSONL with the incident and direction IDs, candidate and EOS status. The collection receipt binds the artifact hashes, private snapshot, image, provider job and reported timings.

For private CPU conversion, use an isolated environment with PyTorch 2.8.0 CPU, the pinned packages in `requirements.txt` and CTranslate2 4.6.2. The command below accepts a new output directory and checks the adapter/config hashes against the collection receipt. It saves a merged BF16 HF checkpoint and a separate int8 CTranslate2 candidate. The export manifest identifies tokenizer, vocabulary, config and binary by SHA-256. Quantization changes numerical behavior and requires separate output checks before any direction can be enabled.

```sh
python translator_pilot/compute/export_ct2.py .data/mt-pilot/results/adapter .data/mt-pilot/results-receipt.json .data/mt-pilot/converted
```

## Observed serving parity

Run `bash translator_pilot/compute/parity.sh /path/to/frozen-ct2` from the platform root to repeat the CPU-only development check with the worker container. On the first development incident, both releases returned a completed translation for all 20 directions. One frozen output and seven adapted outputs exactly matched their respective BF16 GPU strings. See `dev-serving-parity.json` for identities. CPU int8 uses beam 4 with a 512-token ceiling; GPU BF16 uses greedy decoding with a 160-token ceiling. The frozen CT2 release comes from a separate community conversion. String inequality alone does not measure semantic fidelity, and this check cannot distinguish quantization effects from decoding or conversion differences.
