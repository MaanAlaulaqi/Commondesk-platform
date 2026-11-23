# Orientation and routing checkpoint

Local review branch `orientation-directory-20261123` starts at the production baseline `7a031ee`. The translator pilot has its own checkout and history. No push, deployment, booking, provider contact or spend was part of this checkpoint.

## Page orientation

Explore, Search, Insights, Report and case detail now have a plain-language sentence immediately beneath the page title in English, Arabic, Hindi, Thai and Urdu. Archive detail has its own wording. Insights describes the selected collection and filters, including category, week and urgency. Its help explains chart drill-down and unreviewed urgency. Help opens on pointer hover and keyboard focus, works by touch, and can be dismissed with Escape or outside interaction. A named, focusable button exposes its expanded state and its explanation; the explanation appears inline.

## Service behavior

At the baseline, the API returned one fixed RTA Madinati option for eligible public cases. Primary seeds used their stored per-case eligibility. Live footpath and transit cases followed category rules. The review API saved the selected ID and a review event. The guidance worker could cite the RTA passage but had no private catalog.

The branch adds private plumbing and private electrical categories, a reviewed property context, and an operator-supplied directory. A clerk saves scope corrections first, then selects from the refreshed eligible list. The API validates the effective case at write time. Unknown property scope, public assets and urgent or recognized emergency cases are excluded from private suggestions. Restricted district lists require a matching saved district. Feedback, suggestions, seeds and archive references do not receive private providers. Legacy public RTA eligibility is preserved. A local audit of all 2,348 primary seed records matched all 373 original RTA offers and all 1,975 exclusions.

A selection records local routing intent and an event in one transaction. The UI names the selection in the case timeline. Guidance links to the eligible directory item and, for a recorded current selection, to its exact history event. A scope correction can clear an obsolete selection while preserving the prior event. Real provider entries are absent from the shipped catalog. The sample configuration contains two disabled fictional entries. [Configuration and API contract](../api/README.md) · [Candidate research for Maan](service-directory-review.md)

## Tested locally

| Check | Observation |
|---|---|
| Production frontend build | TypeScript and Vite passed. Vite flagged the main bundle size as an advisory. |
| Browser matrix | Chromium 159.0.8154.6, desktop 1440×960 and emulated touch 390×844, five languages, five pages plus the archive detail variant. All 60 combinations passed. Arabic and Urdu used RTL document direction. |
| Help and accessibility | Mouse hover/click, Tab/focus, Enter, Space, Escape, retained focus, touch toggle and outside dismissal passed. All 24 whole-page axe scans passed the enabled WCAG A/AA rule tags with help open and closed in desktop English and mobile Arabic. No unexpected requests or JavaScript errors. Physical-device and spoken screen-reader testing remain outstanding. |
| Directory UI | Fictional entry and directory disclaimer rendered. Context, category and urgency edits each cleared the pending selection. Archive detail omitted the private option. Historical selection wording and exact linked-item focus passed. |
| API and grounding | Directory and existing API contract suites passed. Tests exercised both private trades, five-language intake and cited answers, public/private exclusions, urgency, district restrictions, stale revisions, idempotent replay, unavailable entries, automatic clearing and original event retention. |
| Existing databases | Upgraded an isolated baseline database containing an existing RTA-selected case in both SQLite and PostgreSQL 17. Running the migration twice preserved the case, selection and eligibility. Production databases were untouched. |

Reproduce the browser checks from `web/` with dependencies and Playwright Chromium installed using `npm run build`, then `node scripts/verify-orientation.mjs`. Set `EVIDENCE_FILE` to save the result. The browser uses local synthetic fixtures. From the project root run `PYTHONPATH=api:. python api/test_service_directory.py` and `PYTHONPATH=. python api/test_contracts.py` in the API environment.

## Launch choices

The branch can be reviewed with the private directory empty. A later private listing needs Maan’s approval for its actual trade, coverage and first-party link, followed by a reviewed catalog configuration. A dry merge check with the translator branch flagged overlaps in the case detail component and API documentation. If both changes ship together, retain the translator’s independent Report and Answer language controls alongside this branch’s orientation, timeline and routing controls, and rerun both browser suites.
