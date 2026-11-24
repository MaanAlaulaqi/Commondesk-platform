# Release verification

## Production frontend

[Open CommonDesk](https://commondesk.maanalaulaqi.dev/). The Railway service `commondesk-web` builds the Dockerfile in `/web` from GitHub `main`. Its temporary Railway domain also serves the application. Caddy forwards browser requests under `/api/` to the existing private API. At cutover the custom hostname passed TLS verification, showed 2,348 seed submissions, reopened a case on refresh and returned 20 search results. GitHub Actions continues to run the service checks.

If web hosting fails, use the [last published Pages site](https://maanalaulaqi.github.io/Commondesk-platform/) with the existing public API. To resume publishing there, restore `.github/workflows/pages.yml` from commit `fb5e6bc` in a PR and run **Release web** on main. Keep the Pages API origin repository variables available for this fallback. If an issue affects only the custom hostname, use the [Railway service domain](https://commondesk-web-production.up.railway.app/).

## Initial release checks (23 November 2026)

The product repository began empty on 23 November 2026. The release owner verified write access, GitHub admin/workflow permissions, Pages workflow setup, Docker Compose, both pinned model snapshots and the seed ZIP checksum. The production Railway project is satisfied-purpose. Its existing Qdrant service hosts the separate read-only archive; product services use dedicated collection names. A new PostgreSQL service has its own persistent volume. Seed files and private data stay outside Git history.

Integration uses two independent stateful services locally (PostgreSQL 17 and Qdrant 1.16.2). Railway uses private service references. The browser receives only the HTTPS API origin. The original Qdrant archive import is operator-owned.

## Ownership checkpoint
Platform root owns migrations sign-off, configuration, release and evidence. Interface, persistence and retrieval leads work in their respective directories. The independent reviewer receives the integrated revision from the shared room. The release owner checks progress during the active run. No new periodic monitor is scheduled by this release.

On 23 November, Railway reported US$0.04 for the existing project at the pre-provisioning checkpoint. No GPU job was launched. The release owner independently verified the archive alias and exact Qdrant count of 1,434,103. Archive points contain report_id and source_offset. The private local source catalog can resolve the original text; the hosted archive intentionally exposes reference IDs when evidence is unavailable. The Dubai seed importer separately verified 2,500 views, 2,348 submissions and 38 photographs against its production collection alias.

## Verified journeys

| Surface | Reproduction | Observation |
|---|---|---|
| Hosted Explore | Open the [public workspace](https://maanalaulaqi.github.io/Commondesk-platform/) or GET [seed insights](https://commondesk-api-production.up.railway.app/api/insights?source=seed) | 2,348 canonical submissions, 2,231 mapped (117 unmapped), 747 awaiting review and 145 high-urgency open. |
| Hosted intake and citation | [Open the demonstration receipt](https://maanalaulaqi.github.io/Commondesk-platform/#/case/CD-41DCE36D40A94C24BC77?source=live&receipt=1), ask for status, follow the receipt event | Mobile Chromium completed intake and edit, changed the latitude from 25.215 to 25.216, submitted, refreshed the same ID and opened its highlighted event. Stored longitude 55.300. This is a labeled synthetic case. |
| Layout comparison | From a checkout with web dependencies and Playwright Chromium installed, run `node scripts/check-browser.cjs https://maanalaulaqi.github.io/Commondesk-platform/` | Eight views of the live site captured under .data/browser/: 390×844 and 1440×1000, English/light and Arabic/dark, both map-led and list-led. All eight fetched seed totals from Railway with correct page direction, theme and width. Both layout options remain available. |
| Local empty install | `./scripts/start`, with the worker temporarily stopped for the outage check. Run `python3 scripts/check-intake.py .data/cases.json` against an empty local database. | Five languages, five stable case IDs, five submission replays. Original text, optional pin and five reports survived API restart. |
| Local seed replay | `./scripts/import-seed /path/to/dubai-example-seed-v2.zip`, twice | Both runs returned 2,348 canonical submissions and 2,500 views. Qdrant exact count 2,500. Database holds 38 original photo–report pairs. |
| Clerk and search checks | `python api/verify.py --api http://localhost:8000/api` on a seeded disposable stack | Covers clerk decision, RTA routing, source mismatch rejection, original/translated evidence, multilingual submits, photo and text search, individual event links and abstention. |
| Archive query | POST /api/search with source archive, text “broken drain cover”, limit 3 | Hosted API returned the original three Qdrant IDs, in order, with scores 0.8649347, 0.8622309 and 0.8193587. Source text resolution for the first result was checked with the authorized local catalog. |
| CI and Pages | [Backend and Compose checks](https://github.com/MaanAlaulaqi/Commondesk-platform/actions/workflows/checks.yml) and [web build and publish](https://github.com/MaanAlaulaqi/Commondesk-platform/actions/workflows/pages.yml) | Both passed on the first integrated revision. Pages and Railway were then exercised together in Chromium. |

The warm E5 and DINOv2 model pins, category-head decision, known retrieval failure modes and measured example rankings are in the [model card](../worker/MODEL-CARD.md). Tests on synthetic reports and photographs already present in the demo establish application behavior. Relevance on new incidents needs its own evaluation.

## Deployment and restart

The public frontend defaults to the repository Pages path. The API is [commondesk-api-production.up.railway.app](https://commondesk-api-production.up.railway.app/readyz). Cloud services use private Railway DNS. The API stores report photos in PostgreSQL bytea, alongside durable case data. Seed media enters its private service image only when the operator supplies the pinned demonstration bundle. Worker model files are verified during image build.

With the CLI linked to the production project, run `scripts/deploy-api /path/to/dubai-seed` and `scripts/deploy-worker` to release the corresponding services. Supply a server-side private DATABASE_URL on the API, WORKER_URL on the API, and private QDRANT_URL and QDRANT_API_KEY on the worker. Keep the worker off public networking. Set the API's CORS_ORIGINS to the Pages origin and set COMMONDESK_API_ORIGIN in GitHub repository variables. For seed vectors, run `python -m worker.seed /path/to/dubai-seed` from a trusted environment with its server-side Qdrant configuration. API and vector imports use distinct stores and are replayable. Local web port defaults to 5173; set COMMONDESK_WEB_PORT=5174 if 5173 is already occupied.

The recovery test killed a local API during an active index write. The replacement API recovered in 36.9 seconds including inference. Replaying the job produced exactly one Qdrant point, one case and one receipt event. An earlier compatible API image also read the saved English fixture from the upgraded local PostgreSQL database. The worker renews leases every ten seconds and an abandoned lease expires after thirty seconds.

A separate inspection checked all reachable Git blobs at the reviewed revision, the shipped frontend bundles, the worker network configuration, seed media delivery, the Chromium accessibility tree and keyboard entry into the main content in English and Arabic. No deployment credentials appeared in the inspected bundles or history. The worker had zero public domains and zero TCP proxies. Spoken screen-reader output was not tested. Playwright screenshots are local release artifacts; authorized seed data and rendered development evidence are excluded from Git.

Independent review identified four cases now covered by fixes: global multimodal fusion ranks seed and live candidates together, named-service questions about ineligible cases abstain, duplicate review submissions reuse their prior key, and a changed inference result requires a fresh explicit confirmation. The tested browser replay produced one event after a lost response; another deliberate decision produced a second event. The server-side confirmation digest check returned HTTP 409 for a stale assessment and the browser refreshed the proposal without submitting. Six browser accessibility scans returned zero violations under the configured WCAG A/AA checks.

On a new Railway configuration, run `scripts/configure-health` to configure API and worker readiness. The partial configuration owns only those two services. Preview the plan before applying. Product checks use /readyz with a 180-second startup window. Budget observation at 05:47 GST was about US$0.05 of metered Railway project usage in the current billing period. Hosting continues to accrue usage.
