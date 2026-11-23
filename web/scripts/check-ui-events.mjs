// Use a local web build and invented controls. Never send fixture data off the host.
import assert from "node:assert/strict";
import { chromium } from "playwright";

const origin = new URL(process.argv[2] || "http://127.0.0.1:18194");
assert.ok(["127.0.0.1", "localhost"].includes(origin.hostname));
const browser = await chromium.launch();
try {
  const context = await browser.newContext();
  const observed = [];
  const calls = [];
  const terminal = [];
  await context.route("**/api/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    const id = req.headers()["x-correlation-id"];
    const language = req.headers()["x-ui-language"];
    if (path.endsWith("/ui-events")) {
      observed.push({ id, language, data: req.postDataJSON() });
      return route.fulfill({ status: 503, body: "offline collector" });
    }
    calls.push({ id, language, path });
    return route.fulfill({
      json: {
        total: 0,
        mapped: 0,
        items: [],
        categories: [],
        weeks: [],
        urgencies: [],
      },
    });
  });
  const page = await context.newPage();
  page.on("console", async (msg) => {
    if (
      msg.type() === "info" &&
      (await msg.args()[0]?.jsonValue()) === "ui.click"
    )
      terminal.push(await msg.args()[1].jsonValue());
  });
  await page.goto(origin + "#/search");
  await page.getByRole("link", { name: "Insights", exact: true }).focus();
  await page.keyboard.press("Enter");
  await page.getByRole("heading", { name: "Insights", exact: true }).waitFor();
  await page.waitForFunction(
    () => document.querySelector("h1")?.textContent === "Insights",
  );
  await page.evaluate(() => {
    const button = document.createElement("button");
    button.id = "PRIVATE-CASE";
    button.innerText = "PRIVATE-TEXT";
    button.setAttribute("data-ui-action", "PRIVATE-VALUE");
    document.querySelector("main").append(button);
  });
  await page.locator("#PRIVATE-CASE").click();
  const language = page.locator(".header-settings select").first();
  await language.focus();
  await language.press("ArrowDown");
  await page.waitForFunction(() => document.documentElement.lang === "ar");
  await page.evaluate(() => {
    const out = document.createElement("a");
    out.href = "https://external.invalid/PRIVATE-CASE";
    out.id = "external";
    out.target = "_blank";
    out.innerText = "PRIVATE-EXTERNAL";
    document.querySelector("main").append(out);
  });
  let externalHeaders;
  await context.route("https://external.invalid/**", async (route) => {
    externalHeaders = route.request().headers();
    return route.fulfill({ body: "external fixture" });
  });
  await page.locator("#external").click();
  const end = Date.now() + 2000;
  while (
    (!externalHeaders || observed.length < 4 || terminal.length < 4) &&
    Date.now() < end
  )
    await new Promise((resolve) => setTimeout(resolve, 15));
  assert.deepEqual(
    observed.map((x) => x.data.action),
    ["insights_open", "control_button", "interface_language", "control_link"],
  );
  const id = observed[0].id;
  assert.match(
    id,
    /^[0-9a-f]{8}-[0-9a-f]{4}-4[0-9a-f]{3}-[89ab][0-9a-f]{3}-[0-9a-f]{12}$/,
  );
  assert.ok(
    observed.every(
      (x) => x.id === id && Object.keys(x.data).join(",") === "action",
    ),
  );
  assert.ok(calls.length > 0 && calls.every((x) => x.id === id));
  assert.equal(externalHeaders["x-correlation-id"], undefined);
  assert.equal(externalHeaders["x-ui-language"], undefined);
  assert.deepEqual(
    observed.map((e) => e.language),
    ["en", "en", "ar", "ar"],
  );
  assert.deepEqual(
    terminal,
    observed.map((x) => ({
      action: x.data.action,
      correlationId: x.id,
      uiLanguage: x.language,
    })),
  );
  assert.ok(!JSON.stringify(terminal).includes("PRIVATE"));
  const other = await context.newPage();
  await other.goto(origin + "#/search");
  await other.locator('nav a[href="#/insights"]').click();
  const deadline = Date.now() + 2000;
  while (observed.length < 5 && Date.now() < deadline)
    await new Promise((resolve) => setTimeout(resolve, 10));
  assert.equal(observed.length, 5);
  assert.notEqual(observed.at(-1).id, id);
  assert.equal(calls.at(-1).language, "ar");
  const stored = await other.evaluate(() => [
    ...Object.values(localStorage),
    ...Object.values(sessionStorage),
  ]);
  assert.ok(!stored.includes(id) && !stored.includes(observed.at(-1).id));
  console.log(
    "Keyboard and pointer events, safe fallback, private field exclusion, API correlation, tab isolation, external navigation and collector failure passed.",
  );
} finally {
  await browser.close();
}
