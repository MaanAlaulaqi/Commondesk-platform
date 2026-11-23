# CommonDesk implementation agreement
| Owner | Path or responsibility |
|---|---|
| Interface | web/ React, TypeScript, map, workflows, accessibility |
| Persistence | api/ HTTP API, migrations, durable queue, media, seed import |
| Retrieval | worker/ pinned encoders, indexing, inference and search |
| Integration | Root configuration, deployment, CI, acceptance and release |
| Independent reviewer | Cross-stack journeys and release checks |

API prefix /api. GET /cases (filters, response {items,total}), /cases/{id}, /insights; POST /cases, /proposal, /cases/{id}/review, /search, /answer. GET /media/{id}. Case summaries use id, text, language, category, urgency, status, district, latitude, longitude, source. POST search {text,source,filters,photo} returns {items,total}. Upload via POST /media multipart file; photo is returned media ID. Browser routes use hashes on Pages. Sources seed, live, archive. Qdrant collections commondesk_seed_v1 and commondesk_live_v1; archive alias read-only. Integration owns service configuration; leads may add endpoints and must document and communicate exact contracts.
