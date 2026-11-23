# CommonDesk original-report translation pilot

**Decision, 23 November 2026. Zero directions qualify for production.** Arabic → English earned five concordant passes in both arms. It qualifies for additional bilingual evaluation only. Every other adapter direction had at least one material failure or unresolved judgment. The working platform feature and candidate remain on a local branch. The live platform, archive and Qdrant were untouched.

## Data and training

All 35 incidents are invented. Each has five model-authored language views. Grouped incident splits of 25/5/5 expanded to 500 training, 100 development and 100 held-out ordered pairs. Each of the 20 directions has 25/5/5 examples. Across the 175 distinct source views there were zero normalized text duplicates and zero missing expected scripts. Source views were 32–112 characters. Script coverage alone cannot establish semantic accuracy or distinguish Arabic from Urdu. Neither professional references nor resident traffic entered the experiment. The same five test incidents occur across all directions, so the 100 rows provide five independent incident families.

The signed freeze preceded the GPU run. Its SHA-256 is `bb8f3d63b7cbc88783bd105443ed3f16cadd3613bf9d3654ce14e6ab78aa5fbd`. The private Hugging Face dataset stage is `42b9473c2b2ae751b0b616c00fd49dd82747c00e`. The frozen control and PEFT adapter used `google/madlad400-3b-mt` at `fa184c675da0b5c9e1c8694fccd4e12e2d422094`, the same tokenizer and greedy BF16 decoding. A fixed one-epoch rank-8 attention adapter trained 4,718,592 parameters in 63 updates. No test result was used for fitting, checkpoint selection or a retry. The private adapter SHA-256 is `92bc8372ccde7a24577c363d22147443e5e837f0a28765b911df631233029350`.

HF job `6b03a9b18d268c0fbd23547e` completed in 517 running seconds plus seven scheduling seconds on one A100 80 GB. Peak allocated GPU memory was 9.10 GB. Nine rounded running minutes at $0.041667/minute imply approximately $0.38 of compute. The invoice was not observed. The source notebook is saved in the research workspace under `colab-files/18_commondesk_madlad_adapter.ipynb`. Reproduction instructions and artifact digests are in [the training record](compute/README.md) and [the provider receipt](compute/observed.json).

## Blinded fidelity results

GPT-6.2 Astra and GPT-6.2 Sol each returned 200 yes/no judgments with short reason tags. Each reader received a separately shuffled synthetic-only packet with opaque identifiers. Both operated in fresh sessions without model identities, references, tools, private complaints or photos. This was automated review within one provider family. Concordant yes counted as pass, concordant no as fail, and disagreement as unresolved.

| BF16 condition | Pass | Fail | Unresolved | Dev macro chrF++ | Test macro chrF++ |
|---|---:|---:|---:|---:|---:|
| Frozen | 25 | 69 | 6 | 45.99 | 43.67 |
| Adapter | 29 | 69 | 2 | 46.39 | 45.10 |

Paired across the same 100 inputs, the adapter had two wins, two losses, 90 ties and six unresolved comparisons. Across arms, 52 of 100 output strings were identical. Two of those 52 earned different consensus outcomes (unresolved for the control, pass for the adapter), illustrating judge variability. Each arm reached EOS on every test output. Common adapter rejection tags included place (83), omitted content (55), hazard (50), requested action (38), number (15), negation (4) and unit (3). Counts are reader tags and can overlap. The aggregate gives no basis to switch to the adapter for production.

Per-direction counts are **pass / fail / unresolved**, each out of five. chrF++ measures surface overlap with the model-authored target wording.

| Direction | Frozen | Adapter | Frozen chrF++ | Adapter chrF++ |
|---|---:|---:|---:|---:|
| ar → en | 5/0/0 | 5/0/0 | 69.56 | 69.56 |
| ar → hi | 0/5/0 | 1/4/0 | 38.03 | 48.65 |
| ar → th | 1/3/1 | 0/4/1 | 36.66 | 34.70 |
| ar → ur | 0/5/0 | 0/5/0 | 31.69 | 32.19 |
| en → ar | 3/2/0 | 4/1/0 | 50.68 | 50.37 |
| en → hi | 1/4/0 | 1/4/0 | 48.76 | 49.79 |
| en → th | 2/2/1 | 3/2/0 | 33.90 | 35.92 |
| en → ur | 1/4/0 | 0/5/0 | 34.32 | 34.74 |
| hi → ar | 3/2/0 | 3/2/0 | 38.94 | 38.19 |
| hi → en | 3/2/0 | 3/2/0 | 72.42 | 72.42 |
| hi → th | 0/3/2 | 2/3/0 | 35.06 | 34.68 |
| hi → ur | 0/5/0 | 0/5/0 | 41.32 | 46.91 |
| th → ar | 1/4/0 | 1/4/0 | 31.93 | 28.86 |
| th → en | 1/3/1 | 1/3/1 | 54.37 | 55.97 |
| th → hi | 0/5/0 | 0/5/0 | 41.68 | 45.02 |
| th → ur | 0/5/0 | 0/5/0 | 27.01 | 34.25 |
| ur → ar | 1/4/0 | 1/4/0 | 34.02 | 34.39 |
| ur → en | 2/3/0 | 2/3/0 | 63.66 | 65.44 |
| ur → hi | 1/4/0 | 1/4/0 | 60.11 | 60.73 |
| ur → th | 0/4/1 | 1/4/0 | 29.31 | 29.24 |

## Platform and serving checks

The detail page keeps the original visible. Selecting another Report language reuses a stored wording, otherwise the case API requests an allowed machine translation from the private worker and caches it by case, source digest, languages and inference release. A revoked direction cannot use an older machine cache entry. Worker failures leave the original available. Ask uses an independent Answer language. An archive reference without original text offers no translation control.

Fresh local Docker containers used a two-CPU quota and 8 GiB memory limit with locally available weights. The 20 warm samples comprise one short invented input per direction. The first generation was English → Hindi. Cold startup includes artifact verification but excludes image building and model download.

| Measurement | Frozen CT2 INT8 | Adapted CT2 INT8 |
|---|---:|---:|
| Container start to ready | 8.30 s | 5.52 s |
| First generation | 4.66 s | 3.55 s |
| Warm p50 / p95 | 4.26 / 5.11 s | 3.46 / 4.22 s |
| Longer synthetic input | 22.60 s | 21.21 s |
| Peak container memory including charged file cache | 5.02 GiB | 3.36 GiB |
| Single fresh case API generation / cache hit | 4.01 s / 8.90 ms | 4.27 s / 9.36 ms |

Each worker completed all 20 warm requests. At four simultaneous cache misses each accepted one and returned HTTP 429 for three. In a separate four-caller same-case API regression, one caller generated and the other three reused the result. Both case API outage checks returned 503 and preserved the original. SQLite, disposable PostgreSQL 17, the web production build, Chromium UI checks and worker boundary tests passed. The build includes optional private Compose wiring. No Railway staging or production deployment was made, and these local timings do not establish a Railway latency or recurring cost.

## Rollout conditions

The served worker uses CT2 INT8 and beam search with beam size four. On the first frozen development incident across 20 directions, the served candidate matched the BF16 adapter output verbatim in 7/20 directions; the served control matched in 1/20. All 40 requests succeeded. These exact-string checks cannot determine semantic equivalence. [Serving comparison](compute/dev-serving-parity.json). Treat each as a distinct inference release from the BF16 greedy arm. Qualifying a direction requires an independently sampled, deployment-representative bilingual evaluation on the exact serving artifact. The protocol requires at least 100 independent incidents per direction, zero critical errors and a one-sided 95% fidelity lower bound of at least 95%. Five passes in five cases give a one-sided lower bound of about 55%. Further development should focus on incident terminology and place/action/quantity preservation using new authorized development data. Keep the frozen test set closed for future tuning. A private Railway staging load test and an approved hosting budget would also precede rollout. The shipped production policy allows zero directions.

[Signed protocol](data/protocol.md) · [Directional scores and ballot digests](evidence/fidelity.json) · [Control serving receipt](evidence/control-serving.json) · [Candidate serving receipt](evidence/candidate-serving.json) · [Worker instructions](../translator/README.md)
