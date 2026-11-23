# CommonDesk

A shared civic reporting workspace in English, Thai, Arabic, Hindi and Urdu. Start on Explore, open a map pin, or file a new report with an optional incident location and photo. Every new submission receives a durable case number. Status answers cite the case's own events.

## Local start

With Docker Compose installed, run `./scripts/start` and open http://localhost:5173. The first build downloads the pinned CPU models. An empty workspace accepts live cases immediately. PostgreSQL stores reports, media, decisions and the indexing queue in a named volume. Qdrant stores rebuildable vectors in its own volume. Stop with `docker compose stop` and resume with `docker compose up -d`.

To add the authorized Dubai demo, run `./scripts/import-seed /path/to/dubai-example-seed-v2.zip`. The importer checks the archive checksum before loading the two stores. It is safe to repeat. Select **Dubai example** to browse 2,348 canonical submissions, including 38 original Bangkok photo–report pairs. Their Dubai pins and workflow fields are simulated. Select **Live workspace** for new submissions.

For a fresh organization's shared workspace, start the stack under a separate Compose project name and unique volumes or deploy a separate instance. Retain the original evidence and review history. Configure private service endpoints and backups before collecting operational reports; the shared release gives every visitor access to all reports and review actions.

## Hosting

GitHub Pages serves the static site under the repository path. Set the repository variable `COMMONDESK_API_ORIGIN` to the API HTTPS origin. The API requires a private PostgreSQL connection and a reachable inference worker. The worker takes a Qdrant URL and server-side API key. The live and seed indexes are separate from the historical archive alias. Source records and model weights stay outside public Git history.

[Implementation agreement](docs/integration.md) · [Release checks](docs/release.md)

An authorized local operator can resolve Bangkok text by mounting a private pinned catalog. Set `COMMONDESK_ARCHIVE_CATALOG` to its absolute path, supply `ARCHIVE_QDRANT_URL` and `ARCHIVE_QDRANT_API_KEY` server-side, and run `docker compose -f compose.yaml -f compose.archive.yaml up -d worker`. The hosted deployment exposes archive reference IDs and scores. The public demo includes the authorized original evidence for the 38 curated Bangkok pairs.

[Open CommonDesk](https://maanalaulaqi.github.io/Commondesk-platform/) · [API readiness](https://commondesk-api-production.up.railway.app/readyz) · [Model versions and limitations](worker/MODEL-CARD.md)
