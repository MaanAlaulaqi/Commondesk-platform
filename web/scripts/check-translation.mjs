// Run against a local built UI. All case and API fixtures are invented.
import assert from "node:assert/strict";
import { chromium } from "playwright";

const base = new URL(process.argv[2] || "http://127.0.0.1:18194");
assert.ok(["localhost", "127.0.0.1"].includes(base.hostname));
const browser = await chromium.launch();
try {
  const page = await browser.newPage();
  const errors = [];
  page.on("pageerror", (error) => errors.push(error.message));
  const requests = [];
  const original = "Synthetic case original.";
  const item = {
    id: "alpha",
    source: "live",
    category: "lighting",
    language: "en",
    text: original,
    original_text: original,
    original_language: "en",
    status: "reported",
    urgency: "low",
    translations: {},
    events: [],
  };
  let resolveSlow;
  const slow = new Promise((resolve) => {
    resolveSlow = resolve;
  });
  await page.route("**/api/**", async (route) => {
    const req = route.request();
    const path = new URL(req.url()).pathname;
    let json = {};
    let status = 200;
    if (path.endsWith("/translation")) {
      const { source, target_language: target } = req.postDataJSON();
      requests.push({ source, target });
      if (target === "hi") await slow;
      if (target === "ur") status = 503;
      if (target === "th") status = 422;
      json = { kind: "machine", text: target + " test output" };
    } else if (path.endsWith("/answer")) {
      requests.push({ answerLanguage: req.postDataJSON().language });
      json = { outcome: "answer", text: "Synthetic reply" };
    } else if (path.endsWith("/cases/alpha")) {
      json = item;
    } else if (path.endsWith("/cases/stored")) {
      json = {
        ...item,
        id: "stored",
        source: "seed",
        translations: { ar: "Stored illustration" },
      };
    } else if (path.endsWith("/cases/missing")) {
      json = {
        id: "missing",
        source: "archive",
        evidence_available: false,
        language: "th",
      };
    }
    await route.fulfill({ json, status });
  });
  await page.goto(base + "#/case/alpha?source=live");
  const report = page.getByLabel("Report language", { exact: true });
  const answer = page.getByLabel("Answer language", { exact: true });
  await report.waitFor();
  assert.equal(await report.inputValue(), "en");
  const originalBlock = page.getByText(original, { exact: true });
  await originalBlock.waitFor();
  await report.selectOption("hi");
  await page.getByText("Loading…", { exact: true }).waitFor();
  assert.equal(await originalBlock.isVisible(), true);
  await report.selectOption("ar");
  await page.getByText("ar test output").waitFor();
  resolveSlow();
  await page.getByText("Machine translation", { exact: true }).waitFor();
  assert.equal(await answer.inputValue(), "en");
  await answer.selectOption("th");
  assert.equal(await report.inputValue(), "ar");
  await page.locator("form").filter({ has: answer }).locator("button").click();
  await page.getByText("Synthetic reply").waitFor();
  assert.ok(requests.some((r) => r.answerLanguage === "th"));
  assert.equal(await page.getByText("hi test output").count(), 0);
  await report.selectOption("ur");
  await page.getByText("Translation unavailable.", { exact: false }).waitFor();
  assert.equal(await originalBlock.isVisible(), true);
  await page.getByRole("button", { name: "Retry" }).waitFor();
  await report.selectOption("th");
  await page.getByText(/No translation is available for this language/).waitFor();
  assert.equal(await originalBlock.isVisible(), true);
  assert.equal(await page.getByRole("button", { name: "Retry" }).count(), 0);
  await report.selectOption("en");
  assert.equal(
    await page.getByText("Machine translation", { exact: true }).count(),
    0,
  );
  const before = requests.length;
  await page.goto(base + "#/case/stored?source=seed");
  await report.selectOption("ar");
  await page.getByText("Stored translation", { exact: true }).waitFor();
  await page.getByText("Stored illustration").waitFor();
  assert.equal(requests.length, before);
  await page.goto(base + "#/case/missing?source=archive");
  await page.getByText(/original complaint text is unavailable/).waitFor();
  assert.equal(await report.count(), 0);
  assert.deepEqual(errors, []);
  console.log(
    "Original visibility; independent Ask; race, outage and stored paths; archive omission passed.",
  );
} finally {
  await browser.close();
}
