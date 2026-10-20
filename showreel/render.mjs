// Renders index.html frame by frame with headless Chromium.
// Usage: node render.mjs <outDir> [workers] [onlyFrames,comma,separated]
import { createRequire } from 'module';
import { mkdirSync } from 'fs';
import { fileURLToPath, pathToFileURL } from 'url';
import path from 'path';

const require = createRequire(import.meta.url);
let playwright;
try { playwright = require('playwright'); } catch { playwright = require('/opt/node-tools/node_modules/playwright'); }

const here = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(process.argv[2] || 'frames');
const workers = Number(process.argv[3] || 4);
const only = process.argv[4] ? process.argv[4].split(',').map(Number) : null;
const TOTAL = 15 * 60;
mkdirSync(outDir, { recursive: true });

const frames = only || [...Array(TOTAL).keys()];
const url = pathToFileURL(path.join(here, 'index.html')).href + '?render';
let done = 0;
const t0 = Date.now();

async function worker(id) {
  const browser = await playwright.chromium.launch();
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => { console.error('page error:', e.message); process.exit(1); });
  await page.goto(url);
  await page.waitForFunction(() => window.ready === true);
  for (let i = id; i < frames.length; i += workers) {
    const f = frames[i];
    await page.evaluate(n => window.renderFrame(n), f);
    await page.screenshot({ path: path.join(outDir, `f_${String(f).padStart(4, '0')}.png`) });
    if (++done % 60 === 0) console.log(`${done}/${frames.length} frames, ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  await browser.close();
}

await Promise.all([...Array(workers).keys()].map(worker));
console.log(`done: ${frames.length} frames in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
