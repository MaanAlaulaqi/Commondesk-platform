# Release verification
The product repository began empty on 23 November 2026. The release owner verified write access, GitHub admin/workflow permissions, Pages workflow setup, Docker Compose, both pinned model snapshots and the seed ZIP checksum. The production Railway project is satisfied-purpose. Its existing Qdrant service hosts the separate read-only archive; product services use dedicated collection names. A new PostgreSQL service has its own persistent volume. Seed files and private data stay outside Git history.

Integration uses two independent stateful services locally (PostgreSQL 17 and Qdrant 1.16.2). Railway uses private service references. The browser receives only the HTTPS API origin. The original Qdrant archive import is operator-owned.

## Ownership checkpoint
Platform root owns migrations sign-off, configuration, release and evidence. Interface, persistence and retrieval leads work in their respective directories. The independent reviewer receives the integrated revision from the shared room. The release owner checks progress during the active run. No new periodic monitor is scheduled by this release.

On 23 November, Railway reported US$0.04 for the existing project at the pre-provisioning checkpoint. No GPU job was launched. The release owner independently verified the archive alias and exact Qdrant count of 1,434,103. Archive points contain report_id and source_offset. The private local source catalog can resolve the original text; the hosted archive intentionally exposes reference IDs when evidence is unavailable. The Dubai seed importer separately verified 2,500 views, 2,348 submissions and 38 photographs against its production collection alias.
