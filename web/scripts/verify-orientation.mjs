// Run from web/ after npm ci and npm run build. No backend or network services required.
import assert from "node:assert/strict";
import { readFile, writeFile } from "node:fs/promises";
import { fileURLToPath } from "node:url";
import { dirname, join } from "node:path";
import { createServer } from "node:http";
import { chromium } from "@playwright/test";
import axe from "axe-core";

const directory = join(dirname(fileURLToPath(import.meta.url)), "../dist");
const staticTypes = {
  js: "text/javascript",
  css: "text/css",
  html: "text/html",
  woff2: "font/woff2",
};
const server = createServer(async (req, res) => {
  const path = new URL(req.url, "http://localhost").pathname;
  if (!/^\/(?:index\.html|assets\/[\w.-]+)?$/.test(path)) {
    res.writeHead(404).end();
    return;
  }
  const file = path === "/" ? "index.html" : path.slice(1);
  try {
    const bytes = await readFile(join(directory, file));
    res.writeHead(200, {
      "content-type":
        staticTypes[file.split(".").at(-1)] || "application/octet-stream",
    });
    res.end(bytes);
  } catch {
    res.writeHead(404).end();
  }
});
await readFile(join(directory, "index.html"));
await new Promise((resolve) => server.listen(0, "127.0.0.1", resolve));
const origin = "http://127.0.0.1:" + server.address().port;
const fixtureService = {
  id: "private_fixture_plumbing",
  name: "Fictional Plumbing Demo",
  kind: "private_directory",
  fictional: true,
  url: null,
};
const source = {
  id: "orientation-demo",
  source: "live",
  text: "A tap in the private courtyard is dripping.",
  language: "en",
  category: "private_plumbing",
  urgency: "moderate",
  service_context: "private_premises",
  revision: 1,
  intent: "complaint",
  status: "reported",
  district: "Dubai",
  latitude: 25.2,
  longitude: 55.3,
  created_at: "2026-01-02T10:00:00Z",
  events: [
    {
      event_id: "synthetic-review",
      at: "2026-01-02T11:00:00Z",
      status: "reported",
      details: {
        routing: { purpose: "routing_intent_only", selected: fixtureService },
      },
    },
  ],
  service_options: [fixtureService],
};
const archive = {
  id: "synthetic-archive",
  source: "archive",
  report_id: "synthetic-archive",
  source_offset: 123,
  evidence_available: false,
  text: "",
  language: "th",
};
const list = { total: 1, items: [source] };
const stats = {
  total: 1,
  mapped: 1,
  unreviewed: 1,
  high_open: 0,
  categories: [{ label: "parks", count: 1 }],
  weeks: [{ label: "2026-01-02", count: 1 }],
  urgencies: [{ label: "low", count: 1 }],
};
const pages = [
  "explore",
  "search",
  "insights",
  "report",
  "case/orientation-demo?source=live",
  "case/synthetic-archive?source=archive",
];
const locales = ["en", "ar", "hi", "th", "ur"];
const transparentTile = Buffer.from(
  "iVBORw0KGgoAAAANSUhEUgAAAAEAAAABCAQAAAC1HAwCAAAAC0lEQVR42mNk+A8AAQUBAScY42YAAAAASUVORK5CYII=",
  "base64",
);
const errors = [],
  failures = [],
  evidence = [];
const browser = await chromium.launch({
  executablePath: process.env.CHROMIUM_PATH || undefined,
});

async function mock(context) {
  await context.route("**/*", async (route) => {
    const req = route.request(),
      url = new URL(req.url());
    if (url.hostname === "tile.openstreetmap.org")
      return route.fulfill({ contentType: "image/png", body: transparentTile });
    if (url.origin !== origin) {
      errors.push("Unexpected remote request " + url.origin);
      return route.abort();
    }
    if (!url.pathname.startsWith("/api/")) return route.continue();
    const fixtures = {
      "/api/cases": list,
      "/api/map": list,
      "/api/facets": { category: ["parks"], district: ["Dubai"] },
      "/api/insights": stats,
      "/api/cases/orientation-demo": source,
      "/api/cases/synthetic-archive": archive,
    };
    const body = fixtures[url.pathname];
    if (!body || req.method() !== "GET") {
      errors.push(
        "Unexpected API request " + req.method() + " " + url.pathname,
      );
      return route.fulfill({ status: 404, json: {} });
    }
    return route.fulfill({ json: body });
  });
}

async function scan(page, route, state) {
  await page.addScriptTag({ content: axe.source });
  const violations = await page.evaluate(async () =>
    (
      await window.axe.run(document, {
        runOnly: {
          type: "tag",
          values: ["wcag2a", "wcag2aa", "wcag21a", "wcag21aa", "wcag22aa"],
        },
      })
    ).violations.map((v) => ({
      id: v.id,
      nodes: v.nodes.map((n) => n.target),
    })),
  );
  if (violations.length) failures.push({ route, state, violations });
}

async function disclosure(page, trigger, action) {
  const id = await trigger.getAttribute("aria-controls");
  assert.ok(id);
  assert.ok((await trigger.innerText()).trim(), "Help needs a visible label");
  const content = page.locator('[id="' + id + '"]');
  const waitOpen = () => content.waitFor({ state: "visible" });
  const waitClosed = () => content.waitFor({ state: "hidden" });
  await waitClosed();
  if (action === "touch") {
    await trigger.tap();
    await waitOpen();
    await trigger.tap();
    await waitClosed();
    await trigger.tap();
    await waitOpen();
    await page.locator("h1").tap();
    await waitClosed();
    return;
  }
  await trigger.hover();
  await waitOpen();
  await content.hover();
  await waitOpen();
  await page.keyboard.press("Escape");
  await waitClosed();
  await trigger.click();
  await waitOpen();
  await trigger.click();
  await waitClosed();
  await page.mouse.move(1, 1);
  // Reach the trigger through real keyboard navigation, including tab-order discovery.
  await page.locator("main").focus();
  for (
    let i = 0;
    i < 180 && !(await trigger.evaluate((el) => el === document.activeElement));
    i++
  ) {
    await page.keyboard.press("Tab");
  }
  assert.ok(
    await trigger.evaluate((el) => el === document.activeElement),
    "Tab must reach the help trigger",
  );
  await waitOpen();
  assert.equal(await trigger.getAttribute("aria-expanded"), "true");
  await page.keyboard.press("Escape");
  await waitClosed();
  assert.ok(
    await trigger.evaluate((el) => el === document.activeElement),
    "Escape must preserve focus",
  );
  await page.keyboard.press("Enter");
  await waitOpen();
  await page.keyboard.press("Space");
  await waitClosed();
  await page.keyboard.press("Space");
  await waitOpen();
  await page.keyboard.press("Tab");
  await waitClosed();
}

async function run(device) {
  const mobile = device === "mobile";
  const context = await browser.newContext({
    viewport: mobile
      ? { width: 390, height: 844 }
      : { width: 1440, height: 960 },
    isMobile: mobile,
    hasTouch: mobile,
    reducedMotion: "reduce",
  });
  try {
    await mock(context);
    const page = await context.newPage();
    page.setDefaultTimeout(4500);
    page.on("pageerror", (err) => errors.push(err.message));
    const summaryText = new Map();
    for (const route of pages) {
      await page.goto(origin + "/#/" + route);
      const strings = new Set();
      for (const lang of locales) {
        await page
          .locator(".header-settings select")
          .first()
          .selectOption(lang);
        const rtl = ["ur", "ar"].includes(lang);
        await page.waitForFunction(
          ([l, d]) =>
            document.documentElement.lang === l &&
            document.documentElement.dir === d,
          [lang, rtl ? "rtl" : "ltr"],
        );
        const summary = page.locator("main h1 + .page-summary");
        await summary.waitFor();
        const text = (await summary.innerText()).trim();
        assert.ok(text.length > 10);
        assert.equal(await page.locator("main .page-summary").count(), 1);
        strings.add(text);
        if (lang === "en" && route.includes("orientation-demo")) {
          assert.match(
            await page.locator(".timeline").innerText(),
            /Routing intent recorded · Private directory suggestion · Fictional Plumbing Demo · Fictional example/,
          );
          const service = page
            .locator('select option[value="private_fixture_plumbing"]')
            .locator("..");
          const option = page.locator(
            'select option[value="private_fixture_plumbing"]',
          );
          assert.match(
            await option.innerText(),
            /Private directory suggestion.*Fictional Plumbing Demo.*Fictional example/,
          );
          await page.getByText(/No one is contacted or booked/).waitFor();
          for (const [name, change, restore] of [
            ["Urgency", "high", ""],
            ["Property or asset", "public_asset", "private_premises"],
            ["Category", "lighting", ""],
          ]) {
            await service.selectOption("private_fixture_plumbing");
            const field = page
              .locator("form")
              .filter({
                has: page.getByRole("button", { name: "Save review" }),
              })
              .getByRole("combobox", { name, exact: true });
            await field.selectOption(change);
            assert.equal(await option.count(), 0);
            await page
              .getByText(
                "Save the changed case details to see eligible service options.",
              )
              .waitFor();
            await field.selectOption(restore);
            assert.equal(await service.inputValue(), "");
          }
          await service.selectOption("private_fixture_plumbing");
          await page.route("**/api/cases/orientation-demo/review", request => {
            assert.equal(request.request().postDataJSON().expected_revision, 1);
            return request.fulfill({ status: 409, json: {detail: "Case changed. Refresh available services."} });
          }, {times: 1});
          const refreshed = page.waitForResponse(response => {
            const path = new URL(response.url()).pathname;
            return path === "/api/cases/orientation-demo" && response.request().method() === "GET";
          });
          await page.getByRole("button", {name: "Save review"}).click();
          await refreshed;
          await page.getByRole("alert").filter({hasText: "Case changed."}).waitFor();
          assert.equal(await service.inputValue(), "");
          await page.evaluate(() => {
            location.hash = "#/case/orientation-demo?source=live&service=private_fixture_plumbing";
          });
          await page.waitForFunction(() => document.activeElement?.id === "service-private_fixture_plumbing");
        }
        if (lang === "en" && route.includes("synthetic-archive"))
          assert.equal(
            await page
              .locator('select option[value="private_fixture_plumbing"]')
              .count(),
            0,
          );
        const previous = summaryText.get(lang) || new Set();
        previous.add(text);
        summaryText.set(lang, previous);
        if (lang !== "en" && lang !== "ar") continue;
        const triggers = page.locator("button.help-trigger:visible");
        const n = await triggers.count();
        assert.ok(n > 0, "Expected a visible help control on " + route);
        assert.equal(
          await page.evaluate(
            () => document.documentElement.scrollWidth <= innerWidth,
          ),
          true,
          route + " overflows " + lang,
        );
        if (lang === (mobile ? "ar" : "en")) {
          for (let i = 0; i < n; i++) {
            try {
              await disclosure(
                page,
                triggers.nth(i),
                mobile ? "touch" : "pointer",
              );
            } catch (err) {
              throw Error(
                [device, route, lang, "help", i, err.message].join(" "),
              );
            }
          }
          await scan(page, route, device + " " + lang + " closed");
          if (n) {
            const help = triggers.first();
            if (mobile) await help.tap();
            else await help.hover();
            await page
              .locator(
                '[id="' + (await help.getAttribute("aria-controls")) + '"]',
              )
              .waitFor();
            await scan(page, route, device + " " + lang + " open");
            if (mobile) await page.locator("h1").tap();
            else await page.keyboard.press("Escape");
          }
          evidence.push({ device, route, lang, visibleHelpControls: n });
        }
      }
      assert.equal(strings.size, 5, "Summary translations " + route);
    }
    for (const [lang, summaries] of summaryText)
      assert.ok(summaries.size >= 5, "Page-specific summaries " + lang);
    assert.ok(
      evidence.some(
        (row) => row.device === device && row.visibleHelpControls > 0,
      ),
    );
  } finally {
    await context.close();
  }
}

try {
  for (const device of ["desktop", "mobile"]) await run(device);
  const result = { browser: browser.version(), evidence, failures, errors };
  if (process.env.EVIDENCE_FILE)
    await writeFile(
      process.env.EVIDENCE_FILE,
      JSON.stringify(result, null, 2) + "\n",
    );
  console.log(JSON.stringify(result, null, 2));
  assert.deepEqual(errors, []);
  assert.deepEqual(failures, []);
} finally {
  await browser.close();
  await new Promise((resolve) => server.close(resolve));
}
