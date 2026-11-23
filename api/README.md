# Case API

FastAPI serves a shared workspace under `/api`. Open `/docs` on the API origin for request schemas. The web frontend sends original-language text and receives a receipt only after the database transaction commits. PostgreSQL stores original wordings, image bytes, immutable event evidence, current decisions, and indexing work.

For the full stack, start with the repository quickstart. For a standalone API, install `requirements.txt` with Python 3.12 and run `uvicorn main:app --port 8000` from this directory. Set `DATABASE_URL` for PostgreSQL, `WORKER_URL` for inference and `CORS_ORIGINS` for browser origins. Without a database URL, the API uses a local SQLite file under `DATA_DIR` (default `data`). Tables and append-only evidence guards are installed at startup. `/healthz` checks the process and `/readyz` checks the case store. A worker outage leaves committed cases available by ID with a pending index state.

| Journey | Request and evidence |
|---|---|
| Intake | `POST /api/media` accepts a bounded JPEG, WebP or PNG and returns its media ID. Send it optionally to `POST /api/proposal`, then `POST /api/cases`. Coordinates require a complete WGS84 pair. The record preserves the resident's text and clerk review starts unconfirmed. |
| Retry a write | Supply `idempotency_key` in JSON or the `Idempotency-Key` header. Retrying a submission or review returns the existing case. Different content under the same key produces HTTP 409. |
| Explore and Insights | `GET /api/cases`, `/api/map`, and `/api/insights` share source, district, status, category, confirmed urgency, language and Dubai-local date filters. `language` requires that a wording exists. `locale` selects localized list wording with original fallback. The map omits unknown points. `GET /api/facets` lists filter choices. |
| Search | `POST /api/search` accepts text, a photo ID, or both, plus scoped filters. Archive lookup is read-only. IDs link to verified historical evidence when the source catalog is configured. |
| Detail and review | `GET /api/cases/{id}` includes original text, translations, proposals and timestamped events. `POST /api/cases/{id}/review` stores decisions independently of the original proposal. A new review can clear a routing choice with `service: "unassigned"`. |
| Report language | `POST /api/cases/{id}/translation` accepts only `source` and `target_language`. The API resolves the original from the case. Results are labeled `original`, `stored`, or `machine`. |
| Grounded answers | `POST /api/answer` supports status, report excerpts and approved service guidance. Each linked status event belongs to one case. A source mismatch returns HTTP 404. Guidance links open the official service page. |

## Data and recovery

From this directory, run `python seed.py /path/to/extracted/dubai-seed` to load the verified v2 case store. Repeat imports preserve clerk edits, reuse image IDs, and restore the source's per-case RTA service eligibility. The worker's separate seed command installs the precomputed search index. A fresh organization can keep the seed empty and begin submitting live cases immediately.

The indexing outbox is committed with each case mutation. Each case has a monotonically increasing revision and one queue row. A worker renews its 30-second claim every 10 seconds while servicing a job. After an API crash, the claim expires within 30 seconds of its last renewal. A restarted worker retries newer metadata and upserts a stable vector ID. Failed dependency calls retry with exponential delays capped at 60 seconds. Check the public `index_status` or inspect scheduled times and attempts in `cd_index_queue`.

## Local acceptance

`python verify.py --api http://localhost:8100/api` uses synthetic live inputs against a local v2 seed, active worker and Qdrant. It checks five languages, coordinate validation, image upload and rejection, cross-language and photo search, concurrent idempotency, review decisions, source-bound citations, abstention and canonical seed totals. Filtered fixture queries provide wiring evidence; standalone retrieval quality is measured separately.

`python verify_recovery.py --worker http://localhost:8001 --qdrant http://localhost:6333` exercises an empty temporary SQLite installation. For PostgreSQL, append `--local-postgres` with a dedicated empty local test database URL. It saves a case through a worker outage, hard-kills the API while a queue lease is active, restarts the API, replays the indexing job, and verifies one persisted case, one event and one exact Qdrant point. These checks create synthetic records and belong in a disposable local stack.

## Reviewed service directory

`GET /api/cases/{id}` returns the effective `service_context`, eligible `service_options`, current `service`, optional `service_event_id` and case revision. Each option has `id`, `name`, `kind`, `fictional` and nullable `url`. Use `POST /api/cases/{id}/review` to save a context or category correction. A subsequent selection can include `expected_revision` to reject a stale screen with HTTP 409. An ineligible option returns HTTP 422. Previously selected options that become ineligible disappear from current guidance, and a review clears the selection while retaining history. Review events retain the routing intent and the option as it appeared when selected. The service directory has no dispatch integration.

Existing public footpath/transit reports may offer RTA Madinati. The seed's original per-case eligibility determines its public option. Historical archive records are read-only. A private directory listing requires a live complaint, a reviewed `private_premises` context, `private_plumbing` or `private_electrical`, and low or moderate assessed urgency. Known public assets, reported hazards and explicit emergencies exclude private listings. Reviewers use context and category to resolve uncertain wording. The input rules cannot recognize every way a resident might describe an emergency. The directory is unsuitable for emergency triage.

Set `SERVICE_CATALOG_PATH` to a read-only local JSON file of reviewed private options. The tracked `service-directory.example.json` contains disabled fictional fixtures. With no file, invalid JSON, duplicate IDs, unsupported fields or invalid entries, the API offers zero private listings. Each entry accepts the following fields.

| Field | Expected value |
|---|---|
| id, name | A stable lowercase `private_` identifier and a display name |
| category | `private_plumbing` or `private_electrical` |
| enabled, fictional | Boolean values, both default to false |
| url, approved_source | For an enabled real provider, the identical reviewed HTTPS source URL in both fields. Fictional fixtures have no external link. |
| allowed_districts | Optional nonempty array of district names. Restricted entries require an exact saved district match after case folding and trimming. Missing or out-of-area districts cannot qualify. Omit only when reviewed coverage has no district restriction. |

A reviewer must verify business identity, offered service, coverage and source before approving a real entry and enabling it in the local configuration. Enabling one registers an informational directory suggestion. A case-specific answer cites the eligible option in that case and any current selection event. A listing implies neither endorsement nor an official referral.

## Private report translation

Set `TRANSLATOR_URL` to the private worker origin for a qualified release. Supported hosts are loopback, the Compose service named `translator`, and Railway private-network names ending in `.railway.internal`. The client disables environment proxies and redirects. It sends the report text and language codes. The report dropdown starts at the original language. A stored wording can be shown even while inference is unavailable. The independent Answer language control belongs to the Ask form.

For generation and machine-cache reads, the API checks the worker's current model revision and allowed directions. It keys a database entry by collection, case, SHA-256 of the original, source language, target language and model revision. A bounded database lease coordinates concurrent requests. Case text and translations stay in the workspace and private worker network. A missing original, an unconfigured worker, or a closed direction returns HTTP 422. The UI keeps the original visible and explains when the requested translation is unavailable. A worker outage returns HTTP 503 and the UI continues showing the original.

Use `python api/test_report_translation.py` from the repository root for the synthetic SQLite/cache regression. Running the same test against a disposable loopback PostgreSQL server via `MT_TEST_POSTGRES_URL` checks database parity. Run `node web/scripts/check-translation.mjs http://127.0.0.1:5173` against the local UI for the browser paths.

For a time-limited observation window, set `TRANSLATOR_EXPIRES_AT` to a Unix timestamp in seconds. Expired or malformed timestamps switch to original-only behavior while preserving stored translations. Use a matching absolute worker shutdown deadline.

The shared worker can host the experimental frozen translator. Set `MT_COHOST=1` on the worker, configure the same random `MT_INTERNAL_TOKEN` (32 or more ASCII characters) on the API and worker, and point the API's `TRANSLATOR_URL` to the existing private worker origin. Leave `TRANSLATOR_EXPIRES_AT` unset for ongoing access. The worker serves the revision manifest while idle. The first uncached translation loads the model into a loopback-only child process. The worker unloads it after ten idle minutes. Stored translations and database cache hits need no inference process. All five languages remain labeled experimental.

## Ordinary server logs

The API emits one JSON line to stdout per completed HTTP request. It uses the registered route template, handler name, method, response status, elapsed milliseconds and a UUIDv4 `correlationId`. Each log record includes the interface language as `uiLanguage`. It is populated only from a single `X-UI-Language` value of `en`, `ar`, `th`, `hi` or `ur`; other inputs and missing headers yield JSON null. The browser interface language is independent of the report language, answer language and browser preference headers. A browser attaches the same random `X-Correlation-ID` to its requests within a tab. If that header is absent or malformed on a normal API call, the server generates a fresh UUIDv4 for that request and returns it in the response. The named operations `proposed`, `detail` and `worker` log elapsed time and whether they returned or raised. Background worker calls receive fresh correlation IDs.

The browser can post `{"action":"report_open"}` to `/api/ui-events` with a UUIDv4 header. A successful submission adds its fixed action label to the same request log line and returns HTTP 204. The API rejects unknown labels, extra fields, arbitrary strings, query parameters and malformed IDs, and bounds accepted bodies to 320 bytes. This route has its own existing per-client request bucket and a global cap of 600 event POST attempts per process per minute. Requests above that global limit get HTTP 429 before logging, so a runaway browser cannot amplify log ingestion. UI action names come from the fixed allowlist in `console_events.py`.

The application keeps no journey table or event export. An operator can search the normal process logs for a correlation ID to follow a tab's work. Application JSON records omit concrete URLs, case IDs, client addresses, request and response contents, and arbitrary headers. Raw Uvicorn access logging is disabled. Hosting-provider access logs, retention and log access controls are managed by the hosting provider separately.
