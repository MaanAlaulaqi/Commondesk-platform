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
| Grounded answers | `POST /api/answer` supports status, report excerpts and approved service guidance. Each linked status event belongs to one case. A source mismatch returns HTTP 404. Guidance links open the official service page. |

## Data and recovery

From this directory, run `python seed.py /path/to/extracted/dubai-seed` to load the verified v2 case store. Repeat imports preserve clerk edits, reuse image IDs, and restore the source's per-case RTA service eligibility. The worker's separate seed command installs the precomputed search index. A fresh organization can keep the seed empty and begin submitting live cases immediately.

The indexing outbox is committed with each case mutation. Each case has a monotonically increasing revision and one queue row. A worker renews its 30-second claim every 10 seconds while servicing a job. After an API crash, the claim expires within 30 seconds of its last renewal. A restarted worker retries newer metadata and upserts a stable vector ID. Failed dependency calls retry with exponential delays capped at 60 seconds. Check the public `index_status` or inspect scheduled times and attempts in `cd_index_queue`.

## Local acceptance

`python verify.py --api http://localhost:8100/api` uses synthetic live inputs against a local v2 seed, active worker and Qdrant. It checks five languages, coordinate validation, image upload and rejection, cross-language and photo search, concurrent idempotency, review decisions, source-bound citations, abstention and canonical seed totals. Filtered fixture queries provide wiring evidence; standalone retrieval quality is measured separately.

`python verify_recovery.py --worker http://localhost:8001 --qdrant http://localhost:6333` exercises an empty temporary SQLite installation. For PostgreSQL, append `--local-postgres` with a dedicated empty local test database URL. It saves a case through a worker outage, hard-kills the API while a queue lease is active, restarts the API, replays the indexing job, and verifies one persisted case, one event and one exact Qdrant point. These checks create synthetic records and belong in a disposable local stack.
