// Run against a seeded local stack. Writes one synthetic local test case only with --write.
import { mkdir, writeFile } from "node:fs/promises";
import { resolve } from "node:path";
import assert from "node:assert/strict";
import { chromium } from "@playwright/test";
import axe from "axe-core";
const origin = process.env.WEB_ORIGIN || "http://localhost:5173";
const out = resolve(process.env.EVIDENCE_DIR || "../.local/browser-evidence");
await mkdir(out, { recursive: true });
const browser = await chromium.launch({
  headless: true,
  executablePath: process.env.CHROMIUM_PATH || undefined,
  args: ["--no-sandbox"],
});
const context = await browser.newContext();
const page = await context.newPage();
page.setDefaultTimeout(10000);
const errors = [];
page.on("pageerror", (e) => errors.push(e.message));
const log = { layouts: [], checks: [], accessibility: [] };
async function open(route) {
  await page.goto(origin + "/#/" + route);
  await page.waitForSelector("main");
}
async function controls(lang, theme) {
  await page.locator(".header-settings select").first().selectOption(lang);
  await page.locator(".header-settings select").last().selectOption(theme);
  await page.waitForFunction(
    ([l, t]) =>
      document.documentElement.lang === l &&
      document.documentElement.dataset.theme === t,
    [lang, theme],
  );
}
async function audit(route) {
  await page.addScriptTag({ content: axe.source });
  const results = await page.evaluate(async () => {
    const r = await window.axe.run(document, {
      runOnly: { type: "tag", values: ["wcag2a", "wcag2aa", "wcag21aa"] },
    });
    return r.violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
    }));
  });
  log.accessibility.push({ route, violations: results });
}
try {
  for (const [device, width, height] of [
    ["desktop", 1440, 1000],
    ["phone", 390, 844],
  ]) {
    await page.setViewportSize({ width, height });
    for (const theme of ["light", "dark"]) {
      const language = theme === "dark" ? "ar" : "en";
      for (const layout of ["map", "list"]) {
        await open("explore");
        await controls(language, theme);
        if (device === "desktop") {
          await page
            .locator(".layout-switch button")
            .nth(layout === "map" ? 0 : 1)
            .click();
        } else {
          await page
            .locator(".mobile-tabs button")
            .nth(layout === "map" ? 0 : 1)
            .click();
        }
        await page.waitForFunction(
          () =>
            document
              .querySelector(".metric strong")
              ?.textContent?.replace(/\D/g, "") === "2348" ||
            document
              .querySelector(".metric strong")
              ?.textContent?.includes("٢"),
        );
        await page.locator(".case-row").first().waitFor({ state: "attached" });
        if (layout === "map" || device === "desktop")
          await page
            .locator(".leaflet-tile-loaded")
            .first()
            .waitFor({ timeout: 20000 });
        await page.evaluate(() => document.fonts.ready);
        await page.waitForTimeout(180);
        const file = device + "-" + theme + "-" + layout + ".png";
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth > innerWidth,
          ),
          false,
          file + " overflow",
        );
        await page.screenshot({
          path: resolve(out, file),
          fullPage: device === "desktop",
        });
        log.layouts.push(file);
      }
    }
  }
  await controls("ar", "dark");
  await page.reload();
  assert.equal(await page.locator("html").getAttribute("dir"), "rtl");
  assert.equal(await page.locator("html").getAttribute("data-theme"), "dark");
  await audit("Explore, phone, Arabic, dark");
  await page.setViewportSize({ width: 1440, height: 1000 });
  await controls("en", "light");
  await open("explore");
  await page.getByRole("button", { name: "Map first" }).click();
  await page.waitForFunction(
    () => document.querySelector(".metric strong")?.textContent === "2,348",
  );
  assert.equal(
    await page.locator(".metric strong").nth(0).innerText(),
    "2,348",
  );
  assert.equal(
    await page.locator(".metric strong").nth(1).innerText(),
    "2,231",
  );
  await page
    .getByRole("combobox", { name: "Category", exact: true })
    .selectOption("lighting");
  await page.waitForFunction(
    () => document.querySelector(".metric strong")?.textContent === "344",
  );
  await page.reload();
  assert.ok(page.url().includes("category=lighting"));
  await page.getByRole("button", { name: "Clear", exact: true }).click();
  await page.waitForFunction(
    () => document.querySelector(".metric strong")?.textContent === "2,348",
  );
  await page.locator(".results-panel .case-title").first().click();
  await page.locator('.floating-case article a[href*="case/"]').last().click();
  await page.locator(".sheet").first().waitFor();
  const id = await page.locator(".detail-head .identifier").innerText();
  await page.goBack();
  await page.locator(".map-pin").first().waitFor({ state: "attached" });
  await page.locator('.map-pin[title="' + id + '"]').click();
  await page.locator(".floating-case .identifier").waitFor();
  log.checks.push({
    case: id,
    journey:
      "Explore totals, category filter, reload, clear, row-to-pin, case detail, back and pin-to-row",
  });
  await open("case/bkk-env-168?source=seed");
  await page.locator("figure img").waitFor();
  for (const lang of ["en", "ar", "ur", "hi", "th"]) {
    await page
      .getByRole("combobox", { name: "Wording", exact: true })
      .selectOption(lang);
    await page.waitForFunction(
      (l) =>
        document.querySelector("select") &&
        document.querySelector('blockquote[lang="' + l + '"]'),
      lang,
    );
  }
  log.checks.push({
    case: "bkk-env-168",
    journey: "Original Thai and four translations, linked source photograph",
  });
  for (const route of [
    "report",
    "search",
    "insights",
    "explore",
    "case/bkk-env-168?source=seed",
  ]) {
    await open(route);
    await page.waitForTimeout(300);
    await audit(route);
  }
  if (process.argv.includes("--write")) {
    assert.ok(
      ["localhost", "127.0.0.1", "[::1]"].includes(new URL(origin).hostname),
      "Write checks require a loopback frontend and local API",
    );
    await page.route("**/api/**", (r) => {
      const u = new URL(r.request().url());
      return r.request().method() === "POST" &&
        !["localhost", "127.0.0.1", "[::1]"].includes(u.hostname)
        ? r.abort()
        : r.continue();
    });
    await open("report");
    await page
      .getByLabel("Describe the issue")
      .fill(
        "Local interface verification. The drain is blocked by leaves after the rain.",
      );
    await page.getByLabel("Use my location").count();
    await page.getByRole("button", { name: "Use my location" }).click();
    await page.getByRole("alert").waitFor();
    const map = page.getByRole("region", { name: "Place incident" });
    await map.click({ position: { x: 210, y: 110 } });
    const handle = page.locator(".location-box .map-pin");
    const box = await handle.boundingBox();
    assert.ok(box);
    await page.mouse.move(box.x + 8, box.y + 10);
    await page.mouse.down();
    await page.mouse.move(box.x + 38, box.y + 34, { steps: 6 });
    await page.mouse.up();
    await page.getByLabel("Latitude").fill("25.238815");
    await page.getByLabel("Longitude").fill("55.313055");
    await page.getByRole("button", { name: "Set pin" }).focus();
    await page.keyboard.press("Enter");
    await page.getByRole("button", { name: "Review report" }).click();
    await page.getByRole("button", { name: "Edit report" }).click();
    await page.getByRole("button", { name: "Review report" }).click();
    await page.getByRole("button", { name: "Confirm and submit" }).click();
    await page.locator(".receipt").waitFor();
    const created = await page.locator(".detail-head .identifier").innerText();
    await page.reload();
    await page
      .getByText("25.238815, 55.313055", { exact: false })
      .first()
      .waitFor();
    log.checks.push({
      case: created,
      journey:
        "Device location denial, map tap, drag, keyboard coordinates, edit, persistence, receipt reload",
    });
    const reviewKeys = [];
    await page.route("**/api/cases/*/review", async (route) => {
      assert.ok(
        ["localhost", "127.0.0.1", "[::1]"].includes(
          new URL(route.request().url()).hostname,
        ),
      );
      reviewKeys.push(route.request().postDataJSON().idempotency_key);
      if (reviewKeys.length === 1) {
        const response = await route.fetch();
        assert.equal(response.ok(), true);
        await route.abort("failed");
      } else await route.continue();
    });
    const before = await page.locator(".timeline li").count();
    await page
      .getByRole("combobox", { name: "Urgency", exact: true })
      .selectOption("high");
    await page.getByRole("button", { name: "Save review" }).click();
    await page.getByRole("alert").waitFor();
    await page.reload();
    await page.getByRole("button", { name: "Save review" }).click();
    await page.getByText("Review saved", { exact: true }).waitFor();
    assert.equal(await page.locator(".timeline li").count(), before + 1);
    assert.equal(reviewKeys[0], reviewKeys[1]);
    await page
      .getByRole("combobox", { name: "Urgency", exact: true })
      .selectOption("low");
    await page.getByRole("button", { name: "Save review" }).click();
    await page.getByText("Review saved", { exact: true }).waitFor();
    assert.notEqual(reviewKeys[1], reviewKeys[2]);
    assert.equal(await page.locator(".timeline li").count(), before + 2);
    log.checks.push({
      case: created,
      journey:
        "Lost clerk-save response after commit, reload, replay same key once; next changed decision generated a fresh key and event.",
    });
  }
  assert.deepEqual(errors, []);
  await writeFile(
    resolve(out, "browser-results.json"),
    JSON.stringify(log, null, 2) + "\n",
  );
  console.log(JSON.stringify(log, null, 2));
} finally {
  await browser.close();
}
