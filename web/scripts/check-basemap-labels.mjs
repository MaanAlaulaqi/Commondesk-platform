import assert from "node:assert/strict";
import { createExpression } from "@maplibre/maplibre-gl-style-spec";
import { labelFields, nameExpression } from "../src/basemapLabels.ts";

const style = { layers: [
  { id: "street", type: "symbol", layout: { "text-field": ["get", "name"] } },
  { id: "town", type: "symbol", layout: { "text-field": "{name}" } },
  { id: "house", type: "symbol", layout: { "text-field": "{housenumber}" } },
  { id: "shield", type: "symbol", layout: { "text-field": "{ref}" } },
  { id: "road", type: "line" },
] };
assert.deepEqual(labelFields(style), ["street", "town"]);
const translations = { en: "Dubai", ar: "دبي", ur: "دبئی", hi: "दुबई", th: "ดูไบ" };
const properties = { name: "Local name" };
for (const [lang, spelling] of Object.entries(translations)) properties["name_" + lang] = spelling;
for (const [lang, spelling] of Object.entries(translations)) {
  const compiled = createExpression(nameExpression(lang), "layers[0].layout.text-field");
  assert.equal(compiled.result, "success");
  assert.equal(compiled.value.evaluate({ zoom: 12 }, { properties }), spelling);
  assert.equal(compiled.value.evaluate({ zoom: 12 }, { properties: { name: "Local name" } }), "Local name");
  assert.equal(compiled.value.evaluate({ zoom: 12 }, { properties: {} }), "");
}
console.log("All five localized labels, local-name fallback and unchanged address/route labels passed.");
