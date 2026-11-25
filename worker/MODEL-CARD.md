# CommonDesk inference release 1

CommonDesk serves two frozen, public upstream encoders. It uses a deterministic multilingual intake rule set and cited answer templates. The model weights are fetched into the worker image from immutable upstream revisions; no training records, weights, or archive files are in product history. Exact file digests are in `model-pins.json`.

| Function | Source | Runtime |
|---|---|---|
| Text retrieval | [intfloat/multilingual-e5-small](https://huggingface.co/intfloat/multilingual-e5-small/tree/614241f622f53c4eeff9890bdc4f31cfecc418b3) | Frozen, CPU, 384 dimensions; prepend `passage: ` when indexing and `query: ` when searching. Tokenize at 192 tokens, mean-pool with attention mask and L2-normalize. |
| Photo retrieval | [facebook/dinov2-small](https://huggingface.co/facebook/dinov2-small/tree/ed25f3a31f01632728cabb09d1542f84ab7b0056) | Supplied image processor, RGB input, last-layer CLS embedding, 384 dimensions, L2-normalize. |
| Suggestions | `civic-intake-rules-v2` | Six civic categories and two private maintenance categories. The latter require explicit private-premises review and eligible intent before the case API can offer any approved directory listing. Matches resident wording across five scripts/languages and some Roman Urdu. Unrecognized or conflicting categories prompt clarification. A matched hazard phrase suggests high urgency and records its text; otherwise a report receives a provisional moderate suggestion. Humans own the final decision. |
| Status | Case-bound events and five localized templates | The latest timestamp determines the status. Simultaneous conflicting updates produce an explicit conflict. Malformed or absent evidence produces abstention. |
| Other answers | Evidence excerpt or RTA Madinati routing reference | The composer quotes the selected source report or links the approved service. Original evidence stays in its source language. It makes no dispatch or completion claims. |

## Project classifier and release decision

The expanded Traffy checkpoint (SHA-256 `22726f51c4bae5098a4e6d69baa4e7befcece18fd710ba21fd21b67fb1391773`) has separate text, photo and fusion states. Reading its saved labels and tensor shapes confirmed 14 Thai Bangkok categories, 14×384 text/photo output matrices and a 14×64 fusion residual. The expanded cohort had 427 Thai training records and 350 validation records. The labels include electricity, flooding and sidewalks; they do not directly represent the six Dubai routing classes or multilingual intake distribution. The project has no validated mapping or calibrated multilingual threshold for deploying those heads on this product. Versioned rules therefore support this release. A later project-trained release needs a matched label ontology, evaluation on the new target languages/issues, permission to distribute its artifacts, and an approved release destination. No new weights are published by this release.

## Search and limitations

Text search uses the complete query embedding for ordinary free text. For a recognized civic term such as sidewalk, the worker averages the embeddings of the equivalent terms in five languages and normalizes the result. If a longer query mentions one recognized topic, the full query contributes 65% and the shared topic contributes 35% before normalization. Queries mentioning multiple topics use the full query. The topic signal applies across the selected collection and does not exclude reports by category or language.

Text and image search use Qdrant cosine similarity within the chosen collection and filters. One seed submission can have five indexed language views. The worker deduplicates by canonical submission ID. Optional photos use a second named vector; a text-only case is eligible for text or combined search. In combined search, weighted reciprocal-rank fusion uses a rank constant of 60, rescales visual ranks to the candidate set and gives text-only reports the two equivalent text contributions used by the research baseline. Bounded top-k requests fuse a candidate window of up to 500 hits per channel. Numbered searches in the demo and live collections rank eligible canonical cases once and briefly cache their IDs and scores. The archive pages its text index directly. Scores compare candidates within one query, not absolute relevance. The case database owns evidence and events. Similarity is never evidence of completion.

Archive lookup uses the read-only `bangkok_archive_e5` alias and validates returned IDs/row offsets against the pinned catalog when provisioned in an authorized environment. The public demo omits the full private catalog. Its archive source exposes references and scores only. The archive has no indexed filter facets or photo vectors. Each result includes a durable detail ID containing its integer Qdrant point offset and original report ID. Detail lookup verifies both values by point ID without scanning the archive. A bare ID from an earlier result also resolves while cached or via a mounted catalog.
 
## Reproduce

From the repository root, Docker Compose builds the CPU worker. `python -m worker.encoders` fetches and verifies weights in `MODEL_DIR`. An offline deployment can instead mount the kit's pinned `models/` and set `MODEL_DIR` to that path. The worker reads `QDRANT_URL`, optionally `QDRANT_API_KEY`, or uses embedded persistent `QDRANT_PATH`. Start exactly one embedded process. For a separately hosted read-only archive, set `ARCHIVE_QDRANT_URL` and `ARCHIVE_QDRANT_API_KEY` server-side. Only set `ARCHIVE_CATALOG` on systems authorized to serve its full text. Use an explicit HTTPS port (443) for Railway. The public API mediates writes, photo normalization, durable jobs and source metadata. Keep worker ports private.

Load the verified seed via `python -m worker.seed /seed` against the service Qdrant or via private `POST /seed` with `SEED_DIR` mounted. The importer checks all three source file digests, upserts language views in bounded batches, checks exact counts and publishes a content-addressed collection behind `commondesk_seed_v1`. Replays preserve reviews. Live inserts use `commondesk_live_v1` and deterministic UUIDs. A fresh workspace can index its first report without importing the seed.

| Private HTTP method | JSON inputs | Output |
|---|---|---|
| GET /readyz | — | Weights present and Qdrant reachable; first inference verifies the model files' SHA-256. |
| POST /index | case with id, source=live, text, language and facets, optional image_b64 | Idempotent canonical indexed ID |
| POST /metadata | id, source, changed category/urgency/status/district | Updated facets on every matching view |
| POST /search | source, text and/or image_b64, optional filters, limit 1–100 | Ranked items with source, ID, score; total is returned hit count |
| GET /archive/{id} | Verified archive ID | Source reference, optional catalog evidence |
| POST /proposal | text, language, optional intent/clarification | Interpretation, matching evidence, provisional urgency/category, clarification and version |
| POST /answer | kind, language, source, optional case_id/events/reports/question | Text, outcome, supporting citation IDs/links |
| GET /healthz | — | Process liveness |

The public API exposes POST /api/search with a server-side photo ID, not base64. For example:

```sh
curl -sS http://localhost:8000/api/search -H 'content-type: application/json' \
  -d '{"source":"seed","text":"broken streetlight","filters":{"language":"ur"},"limit":3}'
```

## Observed release smoke checks

The pinned native CPU worker, Dubai v2 vector caches and Qdrant were exercised together on 23 November. These examples check plumbing and support inspection of misses. They are not a held-out accuracy estimate.

| Input | First result |
|---|---|
| broken streetlight, Urdu filter | DXB-EX-00947, lighting, Urdu |
| چراغ, English filter | DXB-EX-00713, lighting, English |
| naali band hai | DXB-EX-01827, drainage, Urdu |
| blocked drain | DXB-EX-01887, drainage, English |
| شارع streetlight | DXB-EX-00844, lighting, English |
| Search against a nonexistent district | Zero results |
| Thumbnail of bkk-st-009, photo only | bkk-st-009 |
| Same thumbnail and its English complaint, Urdu filter | bkk-st-009, Urdu view |
| broken drain cover, read-only Bangkok archive | 08d0b406b2f45d245d299166, a136134f1fa32263adef20b1, 6e4ed0bd744a3309338749fc; all three resolved by ID and source offset against the authorized local catalog |

The photo example uses a derivative of a known image. Generalization to unseen photos, judgments of urgency, and multilingual search relevance require separate evaluation. Real-world blocked drains and damaged covers have confused the retrieval baseline in development. Users can inspect original reports and correct suggestions.
