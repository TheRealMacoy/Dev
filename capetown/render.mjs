// Renders index.html frame by frame with headless Chromium (WebGL via SwiftShader).
// Usage: node render.mjs <outDir> [workers] [frames: "a,b,c" | "start-end"]
import { createRequire } from 'module';
import { mkdirSync, createReadStream, existsSync, statSync } from 'fs';
import { fileURLToPath } from 'url';
import http from 'http';
import path from 'path';

const require = createRequire(import.meta.url);
let playwright;
try { playwright = require('playwright'); } catch { playwright = require('/opt/node-tools/node_modules/playwright'); }

const here = path.dirname(fileURLToPath(import.meta.url));
const outDir = path.resolve(process.argv[2] || 'frames');
const workers = Number(process.argv[3] || 4);
const sel = process.argv[4];
mkdirSync(outDir, { recursive: true });

const TYPES = { '.html': 'text/html', '.js': 'text/javascript', '.json': 'application/json', '.png': 'image/png', '.jpg': 'image/jpeg', '.bin': 'application/octet-stream' };
const server = http.createServer((req, res) => {
  const p = path.join(here, decodeURIComponent(new URL(req.url, 'http://x').pathname));
  if (!p.startsWith(here) || !existsSync(p) || statSync(p).isDirectory()) { res.writeHead(404); return res.end(); }
  res.writeHead(200, { 'Content-Type': TYPES[path.extname(p)] || 'application/octet-stream' });
  createReadStream(p).pipe(res);
});
await new Promise(r => server.listen(0, '127.0.0.1', r));
const url = `http://127.0.0.1:${server.address().port}/index.html`;

let frames = null, done = 0;
const t0 = Date.now();

async function worker(id) {
  const browser = await playwright.chromium.launch({ args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--ignore-gpu-blocklist'] });
  const page = await browser.newPage({ viewport: { width: 1920, height: 1080 }, deviceScaleFactor: 1 });
  page.on('pageerror', e => { console.error('page error:', e.message); process.exit(1); });
  page.on('console', m => { if (m.type() === 'error' || m.type() === 'warning') console.error('console:', m.text()); });
  await page.goto(url);
  await page.waitForFunction(() => window.ready === true || window.initError, null, { timeout: 600000 });
  const err = await page.evaluate(() => window.initError);
  if (err) { console.error('init failed:', err); process.exit(1); }
  if (!frames) {
    const total = await page.evaluate(() => window.TOTAL_FRAMES);
    if (!sel) frames = [...Array(total).keys()];
    else if (sel.includes('-')) { const [a, b] = sel.split('-').map(Number); frames = [...Array(b - a + 1).keys()].map(i => i + a); }
    else frames = sel.split(',').map(Number);
  }
  for (let i = id; i < frames.length; i += workers) {
    const f = frames[i];
    await page.evaluate(n => window.renderFrame(n), f);
    await page.screenshot({ path: path.join(outDir, `f_${String(f).padStart(4, '0')}.png`) });
    if (++done % 60 === 0) console.log(`${done}/${frames.length} frames, ${((Date.now() - t0) / 1000).toFixed(0)}s`);
  }
  await browser.close();
}

// the first worker decides the frame list; the rest start once it is known
const first = worker(0);
while (!frames) await new Promise(r => setTimeout(r, 200));
await Promise.all([first, ...[...Array(workers - 1).keys()].map(i => worker(i + 1))]);
server.close();
console.log(`done: ${frames.length} frames in ${((Date.now() - t0) / 1000).toFixed(1)}s`);
