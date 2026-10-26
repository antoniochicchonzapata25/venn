// Capture Training screenshots from the running app (logs in as the demo user).
// This performs a REAL short workout session (generate, swap, start, log sets, finish), so the
// completed summary shows a genuine, short actual duration. Demo history sessions are labelled "Demo data".
//   cd frontend && npm run screenshots:training
import { existsSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const here = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.VENN_URL ?? "http://127.0.0.1:8000";
const OUT = path.resolve(here, process.env.OUT ?? "../../docs/evidence");
const executablePath = [process.env.BROWSER, "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe", "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome", "/usr/bin/chromium"].filter(Boolean).find((p) => existsSync(p));
if (!executablePath) throw new Error("No Chrome/Edge found. Set BROWSER=/path/to/chrome.");
mkdirSync(OUT, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const shot = async (page, name, fullPage = false) => { await page.screenshot({ path: path.join(OUT, name), fullPage }); console.log("saved", name); };
const clickText = (page, selector, text) => page.$$eval(selector, (els, t) => {
  const el = els.find((e) => e.textContent.trim().startsWith(t)); if (!el) throw new Error(`no ${t}`); el.click();
}, text);
const fill = async (page, selector, value) => {
  await page.focus(selector);
  await page.keyboard.down("Control"); await page.keyboard.press("A"); await page.keyboard.up("Control");
  await page.keyboard.press("Backspace");
  await page.type(selector, value);
};

const browser = await puppeteer.launch({ executablePath, headless: true, args: ["--no-first-run", "--disable-gpu"] });
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto(BASE, { waitUntil: "networkidle0" });
  const status = await page.evaluate(async () => (await fetch("/api/auth/login", { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: "demo", password: "venn-demo-2026" }) })).status);
  if (status !== 200) throw new Error("demo login failed");

  // Clean up any unfinished session from an earlier run so the flow starts fresh.
  await page.evaluate(async () => {
    const s = await (await fetch("/api/training/summary")).json();
    for (const w of [s.in_progress, s.planned]) if (w) await fetch(`/api/training/workouts/${w.id}`, { method: "DELETE" });
  });

  // 1. Training dashboard (with clearly labelled demo history)
  await page.goto(`${BASE}/training`, { waitUntil: "networkidle0" });
  await page.waitForSelector(".history-list, .card");
  await page.waitForFunction(() => [...document.querySelectorAll("button")].some((b) => b.textContent.trim().startsWith("Generate")));
  await shot(page, "m3_training_dashboard.png");

  // 2. Generate -> complete routine for review
  await clickText(page, "button", "Generate");
  await page.waitForSelector('[aria-label="Why this workout"]');
  await sleep(200);
  await shot(page, "m3_generated_workout.png", true);

  // 3. Replace flow (user-initiated, choose from compatible alternatives)
  await page.$$eval(".exercise-card", (cards) => {
    const card = cards.find((c) => c.querySelector(".ex-num")?.textContent === "4") ?? cards[1];
    [...card.querySelectorAll("button")].find((b) => b.textContent === "Replace").click();
  });
  await page.waitForSelector('[aria-label="Alternatives"] .food-row');
  await sleep(200);
  await shot(page, "m3_replace_exercise.png");
  await page.click('[aria-label="Alternatives"] .food-row');
  await page.waitForFunction(() => !document.querySelector('[aria-label="Replace exercise"]'));

  // 4. Start and log sets
  await clickText(page, "button", "Start workout");
  await page.waitForSelector(".set-form");
  const forms = await page.$$(".set-form");
  const first = forms[0];
  const weightSel = 'input[aria-label^="Weight"]';
  const setValue = async (handle, value) => {
    await handle.focus();
    await page.keyboard.down("Control"); await page.keyboard.press("A"); await page.keyboard.up("Control");
    await page.keyboard.press("Backspace");
    await handle.type(value);
  };
  for (const [w, r] of [["70", "10"], ["70", "9"]]) {
    const form = (await page.$$(".set-form"))[0];
    const inputs = await form.$$("input");
    await setValue(inputs[0], w);
    await setValue(inputs[1], r);
    await (await form.$("button")).click();
    await sleep(700);
  }
  void weightSel; void first;
  await sleep(1500);
  await shot(page, "m3_active_logging.png");

  // phone view of logging
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await sleep(400);
  await shot(page, "m3_active_logging_mobile.png");
  await page.setViewport({ width: 1440, height: 900 });

  // 5. Finish -> summary with planned vs actual
  await (await page.waitForSelector(".finish-row .btn-primary")).click();
  await page.waitForSelector('[aria-label="Workout summary"]');
  await page.evaluate(() => window.scrollTo(0, 0));
  await sleep(300);
  await shot(page, "m3_workout_summary.png");

  // 6. A demo-history session summary (realistic durations, labelled "Demo data")
  const demoId = await page.evaluate(async () => (await (await fetch("/api/training/summary")).json()).history.find((h) => h.is_demo)?.id);
  if (demoId) {
    await page.goto(`${BASE}/training/workouts/${demoId}`, { waitUntil: "networkidle0" });
    await page.waitForSelector('[aria-label="Workout summary"]');
    await shot(page, "m3_demo_history_summary.png");
  }
} finally {
  await browser.close();
}
void fill;
