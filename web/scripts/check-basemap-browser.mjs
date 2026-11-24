// Run with VITE_LOCALIZED_BASEMAP=1 against the local Vite server.
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";

const origin = process.env.WEB_ORIGIN || "http://127.0.0.1:5173";
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
  args: ["--enable-unsafe-swiftshader"],
});
const officialStyle = "https://vector.openstreetmap.org/styles/shortbread/colorful.json";

try {
  const page = await browser.newPage({ viewport: { width: 390, height: 844 } });
  const errors = [];
  page.on("pageerror", (e) => errors.push(e.message));
  await page.goto(origin + "/#/report");
  const selector = page.locator(".header-settings select").first();
  const active = (lang) => page.waitForFunction((value) => {
    const layer = document.querySelector(".leaflet-gl-layer");
    return layer?.dataset.labelField === "name_" + value && layer.style.opacity === "1";
  }, lang, { timeout: 15000 });
  await active("en");
  await page.locator(".case-map").click({ position: { x: 70, y: 70 } });
  await page.locator(".leaflet-marker-icon").waitFor();
  const position = () => page.locator(".location-box input").evaluateAll(
    (inputs) => inputs.slice(0, 2).map((input) => input.value),
  );
  const originalPin = await position();
  assert.ok(originalPin[0] && originalPin[1]);
  for (const [locale, zoomLabel] of Object.entries({
    ar: "تكبير الخريطة", ur: "نقشہ بڑا کریں", hi: "नक्शा बड़ा करें",
    th: "ขยายแผนที่", en: "Zoom in",
  })) {
    await selector.selectOption(locale);
    await active(locale);
    assert.equal(await page.locator(".leaflet-control-zoom-in").getAttribute("aria-label"), zoomLabel);
    assert.deepEqual(await position(), originalPin);
  }
  await page.route(officialStyle, (route) => route.abort());
  const vectorAttempt = page.waitForEvent("requestfailed", { predicate: (req) => req.url() === officialStyle });
  await page.reload();
  await vectorAttempt;
  await page.locator(".leaflet-tile-loaded").first().waitFor({ timeout: 15000 });
  assert.equal(await page.locator(".leaflet-gl-layer").count(), 0);
  assert.deepEqual(errors, []);
  console.log("Five locale switches, preserved pin and raster fallback passed.");
} finally {
  await browser.close();
}
