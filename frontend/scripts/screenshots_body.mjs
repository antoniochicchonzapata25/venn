// Capture Body screenshots (Progress and Recovery) from the running app, logged in as the demo user.
// Read-only: it only shows what is already recorded (the recovery estimate uses the demo user's logged workouts).
//   cd frontend && npm run screenshots:body
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

const browser = await puppeteer.launch({ executablePath, headless: true, args: ["--no-first-run", "--disable-gpu"] });
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900 });
  await page.goto(BASE, { waitUntil: "networkidle0" });
  const status = await page.evaluate(async () => (await fetch("/api/auth/login", { method: "POST",
    headers: { "Content-Type": "application/json" }, body: JSON.stringify({ username: "demo", password: "venn-demo-2026" }) })).status);
  if (status !== 200) throw new Error("demo login failed");

  await page.goto(`${BASE}/body`, { waitUntil: "networkidle0" });
  await page.waitForSelector('[aria-label="Body weight"] .stat-row');
  await sleep(300);
  await shot(page, "m5_body_progress.png", true);

  await page.goto(`${BASE}/body?view=recovery`, { waitUntil: "networkidle0" });
  await page.waitForSelector(".body-figure");
  // select the group with the highest estimated load (falls back to the first assessed one)
  await page.evaluate(() => {
    const order = ["high", "moderate", "low"];
    for (const s of order) {
      const g = document.querySelector(`.body-view .muscle-${s}`);
      if (g) { g.dispatchEvent(new MouseEvent("click", { bubbles: true })); return; }
    }
  });
  await sleep(300);
  await shot(page, "m5_body_recovery.png", true);

  await page.setViewport({ width: 390, height: 844, isMobile: true, deviceScaleFactor: 2 });
  await page.goto(`${BASE}/body?view=recovery`, { waitUntil: "networkidle0" });
  await page.waitForSelector(".body-figure");
  await sleep(300);
  await shot(page, "m5_body_recovery_mobile.png");
} finally {
  await browser.close();
}
