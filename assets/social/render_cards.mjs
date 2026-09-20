import { chromium } from 'playwright';
import fs from 'fs';
const html = fs.readFileSync('iosa_cards_render.html', 'utf8');
const pagina = `<!doctype html><html><head><meta charset="utf-8">${html}</head></html>`;
fs.writeFileSync('iosa_cards_full.html', pagina);
fs.mkdirSync('cards', { recursive: true });
const b = await chromium.launch({ executablePath: '/opt/pw-browsers/chromium' });
for (const n of [1, 2, 3, 4, 5]) {
  const ctx = await b.newContext({ viewport: { width: 1080, height: 1080 }, deviceScaleFactor: 1 });
  const p = await ctx.newPage();
  await p.goto('file://' + process.cwd() + `/iosa_cards_full.html?c=${n}`, { waitUntil: 'networkidle' });
  await p.waitForTimeout(1500);
  await p.screenshot({ path: `cards/iosa-card-${n}.png` });
  await ctx.close();
  console.log('reso', n);
}
await b.close();
