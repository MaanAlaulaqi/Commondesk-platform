# CommonDesk

A shared civic reporting workspace in English, Thai, Arabic, Hindi and Urdu. Start on Explore, open a map pin, or file a new report with an optional incident location and photo. Every new submission receives a durable case number. Status answers cite the case's own events.

## What translates a report?

CommonDesk uses **Google’s MADLAD-400-3B-MT** to translate between English, Thai, Arabic, Hindi and Urdu. When you choose a report language, CommonDesk shows a saved translation if one exists. Otherwise, it translates the report on demand and keeps the original visible alongside it. [Google’s model card](https://huggingface.co/google/madlad400-3b-mt)

**Arabic to English** uses our fine-tuned version of MADLAD. We started with an earlier CommonDesk adapter, a small set of adjustments to the base model, and trained two versions on 64 invented examples each. Both saw the same 32 fictional incident settings. The version running today practiced distinctions like “inspect the valve today” and “do not replace it.” The original Google model handles the other 19 translation directions, including English to Arabic.

**Where we are now.** The Arabic-to-English update is live for multilingual testing. The two fine-tuned versions performed alike on nine development reports, and both missed a separate example where urgency mattered. Bilingual human review is still pending. [Translation model details](translator/README.md)

## Translation models by language

Read the arrows from the original report to the requested translation. **Base MADLAD** means Google’s MADLAD-400-3B-MT with its original weights.

| Language | What serves reports today | Examples from earlier tests |
|---|---|---|
| Arabic | Arabic → English uses the CommonDesk fine-tune. The other directions involving Arabic use base MADLAD, including English → Arabic. | We compared Arabic → English adapters on requests, timing and urgency. NLLB-200 also produced Arabic candidates from Thai reports. |
| Urdu | Base MADLAD in both directions with each of the other four languages. | For Thai → Urdu, we tested NLLB-200 distilled 600M, MADLAD-400-3B-MT and Hy-MT2-7B. Separately, we trained a Hindi/Urdu search adapter to find related reports. It stayed a research model. |
| Hindi | Base MADLAD in both directions with each of the other four languages. | The Thai → Hindi study compared the same three translators and evaluated Hindi results separately from Urdu. |
| Thai | Base MADLAD in both directions with each of the other four languages. | We compared Typhoon Translate 1.5 4B, a Thai–English specialist, with MADLAD and NLLB-200 on Thai → English reports. |
| English | The CommonDesk fine-tune handles incoming Arabic. Base MADLAD handles incoming Hindi, Thai and Urdu, and all four outgoing directions. | English was the target for both the Arabic fine-tune and the Thai translation comparison. |

## Models we’ve used

BERT enters the story through **search**. Our live multilingual E5-small model uses a BERT encoder to turn a query and a report into numbers we can compare. That helps someone find a related report even when they use different words or a different language. MADLAD handles the separate job of writing a translation. [E5’s pinned model configuration](https://huggingface.co/intfloat/multilingual-e5-small/blob/614241f622f53c4eeff9890bdc4f31cfecc418b3/config.json)

| Model | What we used it for | Where it stands |
|---|---|---|
| MADLAD-400-3B-MT | Generates translations between our five languages. | Original model live for 19 directions. |
| CommonDesk MADLAD adapters | Adapted MADLAD to preserve what a resident wants done, to which object, and when. We compared the original, an earlier adapter and two further fine-tunes. | The coached Arabic-to-English version is live. |
| Multilingual E5-small | Finds reports with similar meanings. Earlier experiments also used it to predict report categories. | Original encoder live for text search. |
| DINOv2-small | Finds reports with visually similar photos. | Original encoder live for photo search. |
| XLM-RoBERTa base and ResNet-18 | In an early Bangkok pilot, XLM-RoBERTa read complaint text and ResNet-18 processed photos. We compared how well text alone, photos alone and both together predicted categories. | Historical classification baselines. |
| CommonDesk text, photo and combined classifiers | Trained on Bangkok categories using E5 and DINOv2 features. | Research checkpoints. Live intake uses rules for its own categories. |
| NLLB-200 distilled 600M | Generated candidate translations of Thai complaints into English, Arabic, Hindi and Urdu. | Historical translation comparison. |
| Typhoon Translate 1.5 4B | Tested a Thai–English specialist on the same complaints to see which details survived translation. | Historical translation comparison. |

[Live search models and classifier history](worker/MODEL-CARD.md) · [Translation models](translator/README.md)

## Local start

With Docker Compose installed, run `./scripts/start` and open http://localhost:5173. The first build downloads the pinned CPU models. An empty workspace accepts live cases immediately. PostgreSQL stores reports, media, decisions and the indexing queue in a named volume. Qdrant stores rebuildable vectors in its own volume. Stop with `docker compose stop` and resume with `docker compose up -d`.

To add the authorized Dubai demo, run `./scripts/import-seed /path/to/dubai-example-seed-v2.zip`. The importer checks the archive checksum before loading the two stores. It is safe to repeat. Select **Dubai example** to browse 2,348 canonical submissions, including 38 original Bangkok photo–report pairs. Their Dubai pins and workflow fields are simulated. Select **Live workspace** for new submissions.

To add **DubaiV2Example**, run `./scripts/import-dubai-2024 /path/to/DubaiV2Example` against the local stack. The default directory is `.data/DubaiV2Example`. Select the collection in Explore or Search. It contains 2,500 photo-backed Thai reports from 2024, with stored English, Arabic, Hindi and Urdu translations. The pins represent simulated Dubai neighborhoods. Each search stays within the chosen collection, and each report appears once. [Dataset build and provenance](docs/dubai-2024.md)


For a fresh organization's shared workspace, start the stack under a separate Compose project name and unique volumes or deploy a separate instance. Retain the original evidence and review history. Configure private service endpoints and backups before collecting operational reports; the shared release gives every visitor access to all reports and review actions.

## Hosting

Railway serves the frontend from the `web/` directory on `main`. Caddy serves the site and forwards same-origin `/api/*` requests to the private API. The web service uses `PORT=8080` and `API_UPSTREAM=http://commondesk-api.railway.internal:8000`. Leave `VITE_API_ORIGIN` unset for this build. GitHub Actions runs the service and frontend checks. The API requires a private PostgreSQL connection and a reachable inference worker. The worker takes a Qdrant URL and server-side API key. The live and seed indexes are separate from the historical archive alias. Source records and model weights stay outside public Git history.

[Implementation agreement](docs/integration.md) · [Release checks](docs/release.md)

An authorized local operator can resolve Bangkok text by mounting a private pinned catalog. Set `COMMONDESK_ARCHIVE_CATALOG` to its absolute path, supply `ARCHIVE_QDRANT_URL` and `ARCHIVE_QDRANT_API_KEY` server-side, and run `docker compose -f compose.yaml -f compose.archive.yaml up -d worker`. The hosted deployment exposes archive reference IDs and scores. The public demo includes the authorized original evidence for the 38 curated Bangkok pairs.

[Open CommonDesk](https://commondesk.maanalaulaqi.dev/) · [API readiness](https://commondesk-api-production.up.railway.app/readyz) · [Model versions and limitations](worker/MODEL-CARD.md)
