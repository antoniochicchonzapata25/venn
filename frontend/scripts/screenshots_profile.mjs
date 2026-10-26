// Capture the refreshed design: home, Settings (unit switches, goals), and the onboarding questionnaire.
// Uses the demo user, plus a throwaway account to show first-run onboarding.   cd frontend && npm run screenshots:profile
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
  await page.evaluate(() => fetch("/api/auth/login", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "demo", password: "venn-demo-2026" }) }));

  await page.goto(`${BASE}/`, { waitUntil: "networkidle0" });
  await page.waitForSelector(".day-summary");
  await shot(page, "m35_home.png");

  await page.goto(`${BASE}/settings`, { waitUntil: "networkidle0" });
  await page.waitForSelector('form[aria-label="Profile"]');
  // show imperial units via the switches beside the fields (display only; not saved)
  await page.$$eval('[role="group"] button', (bs) => bs.filter((b) => b.textContent === "ft/in" || b.textContent === "lb").forEach((b) => b.click()));
  await sleep(200);
  await shot(page, "m35_settings.png", true);

  await page.goto(`${BASE}/training`, { waitUntil: "networkidle0" });
  await sleep(800);
  await shot(page, "m35_training_home.png");

  // first-run onboarding with a fresh account
  const ctx = await browser.createBrowserContext();
  const p2 = await ctx.newPage();
  await p2.setViewport({ width: 1440, height: 900 });
  await p2.goto(BASE, { waitUntil: "networkidle0" });
  await p2.evaluate(() => fetch("/api/auth/register", { method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: `newuser_${Date.now() % 100000}`, password: "first-run-demo", display_name: "New user" }) }));
  await p2.goto(`${BASE}/`, { waitUntil: "networkidle0" });
  await p2.waitForSelector('[role="radiogroup"]');
  await p2.$$eval('[role="radio"]', (r) => r[0].click());
  await sleep(150);
  await shot(p2, "m35_onboarding_goal.png");
  await p2.$$eval("button", (bs) => bs.find((b) => b.textContent === "Continue").click());
  await sleep(150);
  await shot(p2, "m35_onboarding_scale.png");
  await ctx.close();

  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await page.goto(`${BASE}/nutrition`, { waitUntil: "networkidle0" });
  await page.waitForSelector(".fab");
  await shot(page, "m35_nutrition_mobile.png");
} finally {
  await browser.close();
}
