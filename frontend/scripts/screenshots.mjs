// Capture evidence screenshots of the running Venn app with a locally installed Chrome or Edge.
//
// Usage (with the app running, e.g. `python run.py`):
//   cd frontend && npm run screenshots
// Options (environment variables): VENN_URL (default http://127.0.0.1:8000), BROWSER (path to chrome/msedge),
// OUT (default ../docs/evidence). Logs in as the demo user and does not save any new entries.
import { existsSync, mkdirSync } from "node:fs";
import path from "node:path";
import { fileURLToPath } from "node:url";
import puppeteer from "puppeteer-core";

const here = path.dirname(fileURLToPath(import.meta.url));
const BASE = process.env.VENN_URL ?? "http://127.0.0.1:8000";
const OUT = path.resolve(here, process.env.OUT ?? "../../docs/evidence");
const CANDIDATES = [
  process.env.BROWSER,
  "C:/Program Files/Google/Chrome/Application/chrome.exe",
  "C:/Program Files (x86)/Microsoft/Edge/Application/msedge.exe",
  "/Applications/Google Chrome.app/Contents/MacOS/Google Chrome",
  "/usr/bin/google-chrome", "/usr/bin/chromium", "/usr/bin/chromium-browser",
].filter(Boolean);
const executablePath = CANDIDATES.find((p) => existsSync(p));
if (!executablePath) throw new Error("No Chrome/Edge found. Set BROWSER=/path/to/chrome.");
mkdirSync(OUT, { recursive: true });

const sleep = (ms) => new Promise((r) => setTimeout(r, ms));
const shot = async (page, name) => {
  const file = path.join(OUT, name);
  await page.screenshot({ path: file });
  console.log("saved", file);
};
const fill = async (page, selector, value) => {
  await page.focus(selector);
  await page.keyboard.down("Control");
  await page.keyboard.press("A");
  await page.keyboard.up("Control");
  await page.keyboard.press("Backspace");
  await page.type(selector, value);
};
const clickText = async (page, selector, text) => {
  await page.$$eval(selector, (els, t) => { const el = els.find((e) => e.textContent.trim() === t); if (!el) throw new Error(t); el.click(); }, text);
};

const browser = await puppeteer.launch({ executablePath, headless: true, args: ["--no-first-run", "--disable-gpu"] });
try {
  const page = await browser.newPage();
  await page.setViewport({ width: 1440, height: 900, deviceScaleFactor: 1 });
  await page.goto(BASE, { waitUntil: "networkidle0" });
  const login = await page.evaluate(async () => (await fetch("/api/auth/login", {
    method: "POST", headers: { "Content-Type": "application/json" },
    body: JSON.stringify({ username: "demo", password: "venn-demo-2026" }),
  })).status);
  if (login !== 200) throw new Error(`demo login failed (${login})`);

  // 1. Nutrition dashboard and chronological food log
  await page.goto(`${BASE}/nutrition`, { waitUntil: "networkidle0" });
  await page.waitForSelector(".log-list, .empty-state");
  await shot(page, "m2_nutrition_dashboard_desktop.png");

  // 2. Add food: recent foods
  await page.click(".desktop-add");
  await page.waitForSelector('[aria-label="Recently used foods"], .empty-state');
  await sleep(200);
  await shot(page, "m2_add_food_recent.png");

  // 3. Search
  await clickText(page, '[role="tab"]', "Search");
  await page.type('input[type="search"]', "chicken breast");
  await page.waitForSelector('[aria-label="Search results"]');
  await sleep(200);
  await shot(page, "m2_add_food_search.png");

  // 4. Quantity step with live preview (not saved)
  await page.click('[aria-label="Search results"] .food-row');
  await page.waitForSelector("#qty");
  await page.select("#unit", "g");
  await fill(page, "#qty", "150");
  await sleep(150);
  await shot(page, "m2_add_food_quantity.png");
  await page.click('[aria-label="Back to food list"]');

  // 5. Barcode typed in manually
  await clickText(page, '[role="tab"]', "Barcode");
  await page.type("#barcode", "888849009305");
  await clickText(page, "button", "Look up");
  await page.waitForSelector('[data-testid="barcode-result"]');
  await shot(page, "m2_barcode_lookup.png");

  // 6. Barcode decoded from an image (an EAN-13 drawn on a canvas, fed to the "Scan from photo" input)
  await fill(page, "#barcode", "");
  await page.evaluate(async () => {
    const L = ["0001101", "0011001", "0010011", "0111101", "0100011", "0110001", "0101111", "0111011", "0110111", "0001011"];
    const G = ["0100111", "0110011", "0011011", "0100001", "0011101", "0111001", "0000101", "0010001", "0001001", "0010111"];
    const R = ["1110010", "1100110", "1101100", "1000010", "1011100", "1001110", "1010000", "1000100", "1001000", "1110100"];
    const PARITY = ["LLLLLL", "LLGLGG", "LLGGLG", "LLGGGL", "LGLLGG", "LGGLLG", "LGGGLL", "LGLGLG", "LGLGGL", "LGGLGL"];
    const code = "0044000065713"; // Oreo, UPC-A 044000065713 as EAN-13
    const d = code.split("").map(Number);
    let bits = "101";
    for (let i = 1; i <= 6; i++) bits += (PARITY[d[0]][i - 1] === "L" ? L : G)[d[i]];
    bits += "01010";
    for (let i = 7; i <= 12; i++) bits += R[d[i]];
    bits += "101";
    const scale = 4, quiet = 40, height = 180;
    const canvas = Object.assign(document.createElement("canvas"), { width: bits.length * scale + quiet * 2, height: height + 40 });
    const ctx = canvas.getContext("2d");
    ctx.fillStyle = "#fff"; ctx.fillRect(0, 0, canvas.width, canvas.height);
    ctx.fillStyle = "#000";
    [...bits].forEach((b, i) => { if (b === "1") ctx.fillRect(quiet + i * scale, 20, scale, height); });
    const blob = await new Promise((r) => canvas.toBlob(r, "image/png"));
    const input = document.querySelector('input[aria-label="Barcode photo"]');
    const dt = new DataTransfer();
    dt.items.add(new File([blob], "barcode.png", { type: "image/png" }));
    input.files = dt.files;
    input.dispatchEvent(new Event("change", { bubbles: true }));
  });
  await page.waitForFunction(() => document.querySelector('[data-testid="barcode-result"]')?.textContent.includes("Oreo"), { timeout: 15000 });
  await shot(page, "m2_barcode_photo_decoded.png");

  // 7. Plausibility check: 150 servings of a protein bar (not saved)
  await fill(page, "#barcode", "888849009305");
  await clickText(page, "button", "Look up");
  await page.waitForFunction(() => document.querySelector('[data-testid="barcode-result"]')?.textContent.includes("Quest"));
  await clickText(page, "button", "Log this product");
  await page.waitForSelector("#qty");
  await fill(page, "#qty", "150");
  await clickText(page, "button", "Add to log");
  await page.waitForSelector(".confirm-box");
  await shot(page, "m2_plausibility_warning.png");

  // 8. Home dashboard with today's real totals
  await page.goto(`${BASE}/`, { waitUntil: "networkidle0" });
  await page.waitForSelector(".day-summary");
  await shot(page, "m2_home_dashboard_desktop.png");

  // 9. Phone layout with the bottom-centre + button
  await page.setViewport({ width: 390, height: 844, deviceScaleFactor: 2, isMobile: true, hasTouch: true });
  await page.goto(`${BASE}/nutrition`, { waitUntil: "networkidle0" });
  await page.waitForSelector(".fab");
  await shot(page, "m2_nutrition_mobile.png");
  await page.click(".fab");
  await page.waitForSelector('[role="dialog"]');
  await sleep(200);
  await shot(page, "m2_add_food_mobile.png");
} finally {
  await browser.close();
}
