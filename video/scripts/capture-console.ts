// Captures the REAL reviewer console (proven/web, served by scripts/py/console_replay.py) through the walkthrough the
// video shows, as 3x screenshots plus the CSS-pixel boxes of the elements the video zooms to, points at or highlights.
//
//   npm run capture   → starts a fresh capture copy (scripts/py/console_replay.py, port 8766, state in .scratch/),
//                       drives it, writes public/capture/*.png and src/data/capture.ts (generated; do not edit),
//                       and stops the copy. The repo's own console (8765) is never touched.
//
// Nothing is mocked in the page: every click, paste and keypress goes to the real console, which calls the real
// API. Two things are added to the page before each screenshot, both visible as what they are: vendor names are
// replaced by a grey "vendor" tag (the synthetic ledgers use real company names, which the video never shows), and
// nothing else. The cursor, zooms and callouts are drawn by the video, not here.
import { spawn } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { chromium, type Page } from 'playwright-core';
import { ROOT, arg } from './lib';

const BASE = arg('url', 'http://127.0.0.1:8766')!;
const OUT = path.join(ROOT, 'public/capture');
const DATA = path.join(ROOT, 'src/data/capture.ts');
// Tall, so the sticky claim-detail pane shows ~1,100 px of its working at once; the video frames 16:9 regions of it.
export const VIEW = { width: 1440, height: 1500, scale: 3 } as const;

interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}
type Boxes = Record<string, Box>;
const shots: Record<string, { file: string; boxes: Boxes; scrollY: number }> = {};

const sleep = (ms: number): Promise<void> => new Promise((r) => setTimeout(r, ms));

/** Vendor names from the three closes' ledgers (the CSV the console itself serves), plus "AWS" from the Lumen text. */
const vendorNames = async (page: Page): Promise<string[]> => {
  const names = new Set<string>(['AWS']);
  for (const id of ['showcase', 'brightfield', 'cobalt']) {
    const csv = await page.evaluate(async (u: string) => (await fetch(u)).text(), `${BASE}/api/ledger.csv?id=${id}`);
    const [head, ...rows] = csv.trim().split('\n');
    const col = head.split(',').indexOf('vendor');
    for (const r of rows) {
      // vendor names in these ledgers contain no commas or quotes
      const v = r.split(',')[col]?.trim();
      if (v) names.add(v.replace(/^"|"$/g, ''));
    }
  }
  return [...names].sort((a, b) => b.length - a.length);
};

/** Replace vendor names in text nodes with a visible grey tag; in the textarea, cover them with the same tag. */
const redact = async (page: Page, names: string[]): Promise<void> => {
  await page.evaluate((list: string[]) => {
    const tag = (): HTMLSpanElement => {
      const s = document.createElement('span');
      s.className = 'video-redacted';
      s.textContent = 'vendor';
      s.style.cssText = 'background:#E5E7EB;color:#6E6A68;border-radius:4px;padding:0 5px;font-style:italic;';
      return s;
    };
    const escape = (t: string): string => t.replace(/[.*+?^${}()|[\]\\]/g, '\\$&');
    const re = new RegExp(`\\b(${list.map(escape).join('|')})\\b`);
    const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
    const hits: Text[] = [];
    for (let n = walker.nextNode(); n; n = walker.nextNode()) {
      const t = n as Text;
      if (t.parentElement?.closest('.video-redacted, textarea, script, style')) continue;
      if (re.test(t.data)) hits.push(t);
    }
    for (const t of hits) {
      let node: Text = t;
      for (let m = re.exec(node.data); m; m = re.exec(node.data)) {
        const after = node.splitText(m.index);
        const rest = after.splitText(m[0].length);
        after.replaceWith(tag());
        node = rest;
      }
    }
    // Text inside a textarea cannot hold a span: measure the word with a mirror and lay a tag over it.
    document.querySelectorAll('.video-redact-cover').forEach((e) => e.remove());
    document.querySelectorAll('textarea').forEach((ta) => {
      if (ta.offsetParent === null) return;
      const cs = getComputedStyle(ta);
      const mirror = document.createElement('div');
      for (const p of ['font', 'letterSpacing', 'lineHeight', 'padding', 'border', 'boxSizing', 'whiteSpace', 'wordWrap', 'overflowWrap', 'tabSize'] as const) {
        mirror.style[p] = cs[p];
      }
      mirror.style.whiteSpace = 'pre-wrap';
      mirror.style.position = 'absolute';
      mirror.style.visibility = 'hidden';
      mirror.style.width = `${ta.clientWidth + parseFloat(cs.borderLeftWidth) + parseFloat(cs.borderRightWidth)}px`;
      const rect = ta.getBoundingClientRect();
      mirror.style.left = `${rect.left + window.scrollX}px`;
      mirror.style.top = `${rect.top + window.scrollY}px`;
      document.body.appendChild(mirror);
      const text = ta.value;
      const g = new RegExp(re.source, 'g');
      let last = 0;
      const marks: HTMLSpanElement[] = [];
      for (let m = g.exec(text); m; m = g.exec(text)) {
        mirror.appendChild(document.createTextNode(text.slice(last, m.index)));
        const s = document.createElement('span');
        s.textContent = m[0];
        mirror.appendChild(s);
        marks.push(s);
        last = m.index + m[0].length;
      }
      mirror.appendChild(document.createTextNode(text.slice(last)));
      for (const s of marks) {
        const r = s.getBoundingClientRect();
        // a plain bar the exact size of the word (the tag's text would not fit in a monospace word this short)
        const cover = tag();
        cover.textContent = '';
        cover.classList.add('video-redact-cover');
        cover.style.position = 'absolute';
        cover.style.left = `${r.left + window.scrollX - 3}px`;
        cover.style.top = `${r.top + window.scrollY - ta.scrollTop}px`;
        cover.style.width = `${r.width + 6}px`;
        cover.style.padding = '0';
        cover.style.height = `${r.height}px`;
        cover.style.lineHeight = `${r.height}px`;
        cover.style.font = cs.font;
        cover.style.zIndex = '5';
        cover.style.boxSizing = 'border-box';
        cover.style.textAlign = 'center';
        document.body.appendChild(cover);
      }
      mirror.remove();
    });
  }, names);
};

/** Boxes (CSS px, page coordinates) of the named targets: a selector, or `text=…` for the smallest element containing it. */
const measure = async (page: Page, targets: Record<string, string>): Promise<Boxes> =>
  page.evaluate((t: Record<string, string>) => {
    const out: Record<string, { x: number; y: number; w: number; h: number }> = {};
    const smallestWith = (needle: string, within: string): Element | null => {
      const root = document.querySelector(within) ?? document.body;
      let best: Element | null = null;
      root.querySelectorAll('*').forEach((e) => {
        const el = e as HTMLElement;
        if (el.offsetParent === null && getComputedStyle(el).position !== 'fixed') return;
        if (!(el.innerText ?? '').toLowerCase().includes(needle.toLowerCase())) return;
        if (!best || (best as HTMLElement).innerText.length > el.innerText.length) best = el;
      });
      return best;
    };
    for (const [name, sel] of Object.entries(t)) {
      let el: Element | null = null;
      if (sel.startsWith('text=')) {
        const [needle, within] = sel.slice(5).split(' @@ ');
        el = smallestWith(needle, within ?? 'body');
      } else el = document.querySelector(sel);
      if (!el) continue;
      const r = el.getBoundingClientRect();
      out[name] = { x: Math.round(r.left + window.scrollX), y: Math.round(r.top + window.scrollY), w: Math.round(r.width), h: Math.round(r.height) };
    }
    return out;
  }, targets);

const detailScrollTo = async (page: Page, heading: string): Promise<void> => {
  await page.evaluate((h: string) => {
    const pane = document.getElementById('claim-detail');
    const target = Array.from(pane?.querySelectorAll('h3') ?? []).find((e) => e.textContent?.trim().startsWith(h));
    if (!pane || !target) return;
    const head = pane.querySelector('.detail-head')?.getBoundingClientRect().height ?? 0;
    pane.scrollTop += target.getBoundingClientRect().top - pane.getBoundingClientRect().top - head - 16;
  }, heading);
  await sleep(200);
};

/** `pane`: scroll the window down so the sticky claim-detail pane stands at full height, then bring that section
 * of the pane to its top. Without it the window is at the top (header, coverage, list). */
const shoot = async (page: Page, names: string[], id: string, targets: Record<string, string>, pane?: string): Promise<void> => {
  await page.evaluate((down: boolean) => window.scrollTo(0, down ? document.documentElement.scrollHeight : 0), Boolean(pane));
  if (pane) await detailScrollTo(page, pane);
  await sleep(250);
  await redact(page, names);
  const file = `${id}.png`;
  // The visible viewport only (what a reviewer sees); the page scroll is recorded so boxes map onto the image.
  const scrollY = await page.evaluate(() => window.scrollY);
  await page.screenshot({ path: path.join(OUT, file) });
  const boxes = await measure(page, targets);
  for (const b of Object.values(boxes)) b.y -= scrollY;
  shots[id] = { file: `capture/${file}`, boxes, scrollY };
  console.log('✓', id, Object.keys(boxes).join(', '));
};

const waitVerified = async (page: Page): Promise<void> => {
  await page.waitForFunction(() => !document.body.classList.contains('loading') && (document.getElementById('verify') as HTMLButtonElement | null)?.disabled === false);
  await sleep(300);
};

const detailTop = async (page: Page): Promise<void> => {
  await page.evaluate(() => { const p = document.getElementById('claim-detail'); if (p) p.scrollTop = 0; });
  await sleep(200);
};

fs.mkdirSync(OUT, { recursive: true });
for (const f of fs.readdirSync(OUT)) if (f.endsWith('.png')) fs.unlinkSync(path.join(OUT, f));

// A fresh capture copy of the console, stopped when this script ends.
const PY = process.env.PROVEN_PYTHON ?? 'python3';
const server = spawn(PY, ['-B', path.join(ROOT, 'scripts/py/console_replay.py'), '--port', new URL(BASE).port], {
  cwd: path.join(ROOT, '.scratch'),
  env: { ...process.env, PYTHONDONTWRITEBYTECODE: '1' },
  stdio: ['ignore', 'pipe', 'inherit'],
});
process.on('exit', () => server.kill());
await new Promise<void>((resolve, reject) => {
  server.stdout.on('data', (d: Buffer) => { if (d.toString().includes('capture console at')) resolve(); });
  server.on('exit', (code) => reject(new Error(`capture console exited (${code})`)));
});

const browser = await chromium.launch();
const ctx = await browser.newContext({ viewport: { width: VIEW.width, height: VIEW.height }, deviceScaleFactor: VIEW.scale, colorScheme: 'light', reducedMotion: 'reduce' });
// tsx (esbuild keepNames) wraps functions in __name(); define it in the page so page.evaluate callbacks run.
await ctx.addInitScript({ content: 'window.__name = (f) => f;' });
const page = await ctx.newPage();
await page.goto(`${BASE}/`);
await waitVerified(page);
const names = await vendorNames(page);
const taught = await page.evaluate(async (u: string) => ((await (await fetch(u)).json()) as { entries: unknown[] }).entries.length, `${BASE}/api/lexicon`);
if (taught > 0) throw new Error('The capture console already has lessons: restart scripts/py/console_replay.py (it starts fresh).');
const lumenText: string = await page.evaluate(() => (document.getElementById('explanation') as HTMLTextAreaElement).value);

// ── 1. Lumen Robotics: paste the commentary, verify, read C1 ─────────────────────────────────────────────────────
const COMMON = { verify: '#verify', extractor: '#extractor', header: '#review-heading', runMeta: '#run-meta', coverage: '#coverage', bar: '#coverage-bar', sidebarLearned: 'button.tab[data-view="learned"]' };
// The console verifies its demo close on load, so the first screen would show that run's verdicts before anything
// is pasted. Start from a real run with nothing to check instead (a heading with no figures: 0 claims), then clear
// the editor. No element is hidden or altered; this is what the console shows after checking a text with no claims.
await page.click('button[data-pane="explanation"]');
await page.click('#edit');
await page.fill('#explanation', 'October 2026 commentary:');
await page.click('#verify');
await waitVerified(page);
await page.click('button[data-pane="explanation"]');
if (await page.locator('#edit').textContent() !== 'Show checked text') await page.click('#edit');
await page.fill('#explanation', '');
await page.evaluate(() => { const ta = document.getElementById('explanation') as HTMLTextAreaElement; ta.style.height = '560px'; });
await shoot(page, names, 'lumen-empty', { ...COMMON, editor: '#explanation', editBtn: '#edit' });
await page.focus('#explanation');
await page.evaluate((t: string) => navigator.clipboard?.writeText(t).catch(() => undefined), lumenText);
await page.fill('#explanation', lumenText); // the paste itself: the same text, set in one step
// The editor is resizable by its handle; drag it open to the text's height, as a reviewer would, and show the top.
await page.evaluate(() => { const ta = document.getElementById('explanation') as HTMLTextAreaElement; ta.style.height = `${ta.scrollHeight + 4}px`; ta.scrollTop = 0; });
await shoot(page, names, 'lumen-pasted', { ...COMMON, editor: '#explanation' });
await page.click('#verify');
await waitVerified(page);
if (await page.locator('#edit').textContent() === 'Show checked text') await page.click('#edit');
await shoot(page, names, 'lumen-annotated', { ...COMMON, annotated: '#annotated', c1Sentence: 'text=Legal costs rose $90K @@ #annotated', c2Sentence: 'text=Marketing spend increased @@ #annotated', c4Sentence: 'text=Software & subscriptions @@ #annotated' });
await page.click('button[data-pane="claims"]');
await detailTop(page);
await shoot(page, names, 'lumen-claims', {
  ...COMMON,
  claims: '#claims',
  c1Row: '#claims li:first-child',
  detail: '#claim-detail',
  detailReason: '#claim-detail .claim-reason, #claim-detail h2 + *',
  recon: 'text=Reconstruction @@ #claim-detail',
  rowLedger: 'text=Sep 2026 $9,500 @@ #claim-detail',
  rowStated: 'text=rose, change $90K @@ #claim-detail',
  rowReclass: 'text=+$90,000 @@ #claim-detail',
});
await detailScrollTo(page, 'Findings');
await shoot(page, names, 'lumen-findings', { ...COMMON, detail: '#claim-detail', findings: 'text=Findings @@ #claim-detail', misbooked: 'text=TX-2068 @@ #claim-detail', tx2064: 'text=TX-2064 @@ #claim-detail' }, 'Findings');

// ── 2. Brightfield Health: Claude proposes (replayed), a claim waits, the gate, confirm once ──────────────────────
await page.selectOption('#scenario', 'brightfield');
await waitVerified(page);
await page.selectOption('#extractor', 'claude');
await sleep(200);
await shoot(page, names, 'bright-extractor', { ...COMMON, note: '#extractor-note', modelField: '#model-field' });
await page.click('#verify');
await waitVerified(page);
await detailTop(page);
await shoot(page, names, 'bright-claims', {
  ...COMMON,
  note: '#extractor-note',
  claims: '#claims',
  c1Row: '#claims li:first-child',
  detail: '#claim-detail',
  searched: 'text=Searched @@ #claim-detail',
  matched: 'text=Matched @@ #claim-detail',
});
await detailScrollTo(page, 'Findings');
await shoot(page, names, 'bright-findings', { ...COMMON, detail: '#claim-detail', findings: 'text=Findings @@ #claim-detail', modelTerms: 'text=model proposed @@ #claim-detail', tx1051: 'text=TX-1051 @@ #claim-detail', tx1061: 'text=TX-1061 @@ #claim-detail' }, 'Findings');
await page.click('button.tab[data-view="learned"]');
await sleep(600);
await page.click('#queue-refresh');
await sleep(1500);
await shoot(page, names, 'queue', { ...COMMON, queue: '#queue', queueItem: '#queue li:first-child', queueCount: '#queue-count', lessons: '#lessons' });
await page.click('button.tab[data-view="review"]');
await sleep(400);
await detailScrollTo(page, 'Resolve');
await shoot(page, names, 'teach-form', { ...COMMON, detail: '#claim-detail', teach: '#claim-detail fieldset.teach', gateBtn: 'text=Check with the safety gate @@ #claim-detail', gate: '#claim-detail .gate' }, 'Resolve');
await page.click('#claim-detail >> text=Check with the safety gate');
await page.waitForFunction(() => /Gate: safe|Gate refuses|Not tested|Refused/.test(document.querySelector('#claim-detail .gate')?.textContent ?? ''), undefined, { timeout: 120000 });
await detailScrollTo(page, 'Resolve');
await shoot(page, names, 'gate-safe', { ...COMMON, detail: '#claim-detail', teach: '#claim-detail fieldset.teach', gate: '#claim-detail .gate', gateBtn: 'text=Check with the safety gate @@ #claim-detail' }, 'Resolve');
await page.fill('#claim-detail textarea[aria-label="Reason for the resolution"]', 'Memos: the Q4 launch campaign.');
await page.check('#claim-detail fieldset.teach input[type="checkbox"]');
await detailScrollTo(page, 'Resolve');
await shoot(page, names, 'teach-ready', { ...COMMON, detail: '#claim-detail', teach: '#claim-detail fieldset.teach', record: '#claim-detail form.resolve > button[type="submit"]', confirm: '#claim-detail fieldset.teach label.check', note: '#claim-detail textarea[aria-label="Reason for the resolution"]' }, 'Resolve');
await page.click('#claim-detail form.resolve > button[type="submit"]');
await page.waitForFunction(() => !(document.getElementById('lesson-notice') as HTMLElement).hidden, undefined, { timeout: 120000 });
await waitVerified(page);
await page.evaluate(() => { const p = document.getElementById('claim-detail'); if (p) p.scrollTop = 0; window.scrollTo(0, 0); });
await shoot(page, names, 'bright-pass', { ...COMMON, notice: '#lesson-notice', claims: '#claims', c1Row: '#claims li:first-child', detail: '#claim-detail', searched: 'text=Searched @@ #claim-detail', lessonCount: '#lesson-count' });

// ── 3. Cobalt Freight, the next close: Rules (offline), no model ─────────────────────────────────────────────────
await page.selectOption('#extractor', 'rules');
await page.selectOption('#scenario', 'cobalt');
await waitVerified(page);
await page.click('button[data-filter="all"]');
await sleep(300);
const passRow = page.locator('#claims li', { hasText: 'biggest promotion' }).first();
await passRow.click();
await detailTop(page);
await shoot(page, names, 'cobalt-pass', { ...COMMON, claims: '#claims', passRow: '#claims li.active, #claims li[aria-current], #claims li:first-child', detail: '#claim-detail', searched: 'text=Searched @@ #claim-detail', matched: 'text=Matched @@ #claim-detail', lessonCount: '#lesson-count' });
await page.click('button.tab[data-view="learned"]');
await sleep(600);
await shoot(page, names, 'lessons', { ...COMMON, lessons: '#lessons', lesson: '#lessons .lesson' });

await browser.close();
server.kill();

const header = `// GENERATED by scripts/capture-console.ts from the real console (${BASE}). Do not edit; re-run \`npm run capture\`.\n` +
  `// Boxes are CSS px in the screenshot's viewport (${VIEW.width}×${VIEW.height}); the PNGs are ${VIEW.scale}x.\n`;
fs.writeFileSync(DATA, `${header}export const CAPTURE_VIEW = ${JSON.stringify(VIEW)} as const;\n\nexport const SHOTS = ${JSON.stringify(shots, null, 1)} as const;\n\nexport type ShotId = keyof typeof SHOTS;\n`);
console.log('wrote', path.relative(ROOT, DATA));
