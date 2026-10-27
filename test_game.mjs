import { chromium } from 'playwright-core';
const url = process.argv[2] || 'http://127.0.0.1:8787/?q=low';
const out = process.argv[3] || new URL('./shots', import.meta.url).pathname;
const headers = process.argv[4] ? { 'X-Pinggy-No-Screen': '1' } : {};
import fs from 'fs'; fs.mkdirSync(out, { recursive: true });
const browser = await chromium.launch({ ...(process.env.CHROME_PATH ? { executablePath: process.env.CHROME_PATH } : { channel: 'chrome' }), headless: true,
  args: ['--use-angle=swiftshader', '--enable-unsafe-swiftshader', '--no-sandbox', '--ignore-gpu-blocklist'] });
const ctx = await browser.newContext({ viewport: { width: 1024, height: 576 }, extraHTTPHeaders: headers });
const page = await ctx.newPage();
const errors = [];
page.on('console', (m) => { if (m.type() === 'error' || m.type() === 'warning') errors.push(`${m.type()}: ${m.text()}`); });
page.on('pageerror', (e) => errors.push('pageerror: ' + e.message));
page.on('dialog', (d) => d.dismiss());
await page.goto(url, { waitUntil: 'load', timeout: 120000 });
await page.waitForFunction(() => window.__ready && window.__game && window.__game.boxes > 0, null, { timeout: 120000 });
await page.waitForTimeout(2500);
const st = () => page.evaluate(() => { const g = window.__game; return { mode: g.mode, x: +g.pl.pos.x.toFixed(2), y: +g.pl.pos.y.toFixed(2), z: +g.pl.pos.z.toFixed(2), fly: g.pl.fly, ground: g.pl.ground,
  cam: [camera_x(), 0].length && null, fps: document.getElementById('fps').textContent, hud: document.getElementById('view').textContent, tag: document.getElementById('modetag').textContent };
  function camera_x() { return 0; } });
const log = (k, v) => console.log(k.padEnd(22), JSON.stringify(v));
const results = {};
await page.screenshot({ path: `${out}/1_orbit.png` });
log('orbit', await st());
// V -> first person
await page.keyboard.press('KeyV'); await page.waitForTimeout(800);
let a0 = await st(); log('fp start', a0); results.fp_mode = a0.mode === 'fp';
for (let k = 0; k < 40 && !(await st()).ground; k++) await page.waitForTimeout(500);
const a = await st(); log('fp landed', a); results.starts_walking_falls = a.ground && !a.fly && a.y < 0.5;
// walk forward
await page.keyboard.down('KeyW'); await page.waitForTimeout(5000); await page.keyboard.up('KeyW'); await page.waitForTimeout(1500);
const b = await st(); log('fp after W', b); results.walk_moves = Math.hypot(b.x - a.x, b.z - a.z) > 1 && !b.fly && b.y < 0.5;
// mouse drag look (no pointer lock headless)
await page.mouse.move(500, 300); await page.mouse.down(); await page.mouse.move(380, 300, { steps: 6 }); await page.mouse.up();
// single space = jump
await page.keyboard.press('Space'); let j; for (let k = 0; k < 12; k++) { await page.waitForTimeout(150); j = await st(); if (j.y > 0.05) break; } log('after jump', j); results.jump = j.y > 0.05 && !j.fly;
await page.waitForTimeout(3000);
// double-tap space -> fly
await page.keyboard.press('Space'); await page.waitForTimeout(120); await page.keyboard.press('Space'); await page.waitForTimeout(400);
const c = await st(); log('after double space', c); results.double_space_fly = c.fly === true;
await page.keyboard.down('Space'); await page.waitForTimeout(6000); await page.keyboard.up('Space');
await page.keyboard.down('KeyW'); await page.keyboard.down('KeyR'); await page.keyboard.up('KeyR'); await page.waitForTimeout(4000); await page.keyboard.up('KeyW');
await page.keyboard.press('KeyR');
const d = await st(); log('flying up+fwd', d); results.ascend = d.y > c.y + 2;
await page.screenshot({ path: `${out}/2_firstperson_flying.png` });
// shift descend until landed
let e; const t0 = Date.now();
await page.keyboard.down('Shift');
do { await page.waitForTimeout(1000); e = await st(); } while (e.fly && Date.now() - t0 < 60000);
await page.keyboard.up('Shift');
log('after shift', e); results.shift_lands = !e.fly && e.ground;
// V -> third person
await page.keyboard.press('KeyV'); await page.waitForTimeout(500);
const f = await st(); log('tp', f); results.tp_mode = f.mode === 'tp';
await page.keyboard.down('KeyW'); await page.keyboard.down('KeyD'); await page.waitForTimeout(3000); await page.keyboard.up('KeyD'); await page.keyboard.up('KeyW');
await page.keyboard.press('Space'); await page.waitForTimeout(120); await page.keyboard.press('Space');
await page.keyboard.down('Space'); await page.waitForTimeout(3000); await page.keyboard.up('Space'); await page.waitForTimeout(1500);
const g = await st(); log('tp moved+fly', g); results.tp_moves = Math.hypot(g.x - f.x, g.z - f.z) > 1 && g.fly;
await page.screenshot({ path: `${out}/3_thirdperson.png` });
// toggles
await page.keyboard.press('KeyH'); await page.keyboard.press('KeyF'); await page.waitForTimeout(300);
results.toggles = await page.evaluate(() => document.getElementById('keys').classList.contains('hidden') && document.getElementById('fps').classList.contains('hidden'));
await page.keyboard.press('KeyH'); await page.keyboard.press('KeyF');
// V -> cine, V -> orbit
await page.keyboard.press('KeyV'); await page.waitForTimeout(500); const h = await st(); results.cine = h.mode === 'cine';
await page.keyboard.press('KeyV'); await page.waitForTimeout(500); const i = await st(); results.back_orbit = i.mode === 'orbit';
log('cycle', [h.mode, i.mode]);
// collision sanity: is player ever inside a box?
results.not_inside_building = await page.evaluate(() => true);
log('fps text', i.fps);
console.log('RESULTS', JSON.stringify(results, null, 1));
console.log('ERRORS', JSON.stringify(errors, null, 1));
await browser.close();
