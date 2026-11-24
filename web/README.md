# CommonDesk browser interface

Explore is the default route. The desktop default gives the map the larger column and keeps case details alongside it. The list-first option gives more space to multilingual complaints and urgency labels. Both layouts keep the Report action in the header. On phones the map and list share the full width with a switch between them. Returning from a case restores the map viewport; URL filters survive refresh.

The map-first layout was selected after comparing both layouts on the Dubai example. It leaves more room between nearby groups at the initial zoom. The case list remains available for the 117 submissions without positions. List-first is useful for reviewing many case descriptions at once. Both compositions remain available using the Layout control.

## Development

Use the repository quickstart to start the API and model worker, then run:

```sh
cd web
npm ci
npm run dev
```

The dev server proxies `/api` to port 8000. A Pages build uses `VITE_API_ORIGIN` for the public HTTPS service origin. The frontend uses hash routes and relative asset paths so a case link survives a project-site refresh.

## Browser verification

Start the local stack, import Dubai v2 and open the frontend once. With the frontend running, execute:

```sh
cd web
npx playwright install chromium
WEB_ORIGIN=http://localhost:5173 node scripts/verify-browser.mjs --write
```

Use `CHROMIUM_PATH` for an installed Chromium executable. Omit `--write` for the read-only checks. The write check works with a loopback frontend and makes one synthetic report in the local live workspace. Point the frontend at the local API for this check. Use `EVIDENCE_DIR` to select a private output directory, preferably outside the checkout. The runner captures eight desktop/phone layout and theme screenshots alongside a JSON receipt. Browser screenshots can contain demonstration reports; keep them with the private development evidence.

The test checks seed totals, filter state on refresh, map and list selection, original evidence in five language views, optional location, refresh of the receipt, and replay of a review whose first response is lost after commit. It runs axe-core WCAG A/AA checks across six page and language combinations. A passing automated run covers the tested states. Screen-reader usability needs a manual audit.

### Map labels

The Leaflet map uses OpenStreetMap Shortbread vector tiles so switching the
site language updates place and street names in the current view. When a
feature has no name in that language, the local OpenStreetMap name is shown.
The original raster map stays visible while the vector map loads and on
browsers without WebGL. Arabic, Urdu, Hindi and Thai labels use bundled
Noto font files. Keep OpenStreetMap attribution visible and follow the
[vector tile usage policy](https://operations.osmfoundation.org/policies/vector/).

Run `node scripts/check-basemap-labels.mjs` to check the five label expressions
and `WEB_ORIGIN=http://localhost:5173 node scripts/check-basemap-browser.mjs`
to exercise language switching, retained pins and raster fallback in Chromium.

The frontend serves the [CC0 Colorful style](https://vector.openstreetmap.org/styles/shortbread/colorful.json)
and its matching basics sprites from `public/map/`. Only the vector tile requests
go to the upstream tile service. The local style uses browser-rendered glyphs.
