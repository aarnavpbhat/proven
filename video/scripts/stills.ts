// Renders the review stills of the final cut to out/stills/ (full size), plus one contact sheet of them.
// Usage: npm run stills
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { openBrowser, renderStill, selectComposition } from '@remotion/renderer';
import { SCENES, TOTAL_FRAMES } from '../src/timeline';
import { CHROMIUM, ROOT, bundleProject } from './lib';

// One still every 5 s (150 frames), plus the last frame, named by time and scene: the review set for
// docs/critique-log.md.
export const KEY_FRAMES: { frame: number; name: string }[] = [
  ...Array.from({ length: Math.floor((TOTAL_FRAMES - 1) / 150) + 1 }, (_, i) => i * 150 + (i === 0 ? 30 : 0)),
  TOTAL_FRAMES - 1,
].map((frame) => {
  const sc = SCENES.find((x) => frame >= x.from && frame < x.from + x.durationInFrames)?.id ?? 'end';
  return { frame, name: `t${String(Math.round(frame / 30)).padStart(3, '0')}s-${sc}` };
});

const out = path.join(ROOT, 'out/stills');
fs.mkdirSync(out, { recursive: true });
const serveUrl = await bundleProject();
const browser = await openBrowser('chrome', { chromiumOptions: CHROMIUM });
const composition = await selectComposition({ serveUrl, id: 'Demo', puppeteerInstance: browser });
const files: string[] = [];
for (const k of KEY_FRAMES) {
  const output = path.join(out, `${k.name}.png`);
  await renderStill({ chromiumOptions: CHROMIUM, puppeteerInstance: browser, composition, serveUrl, output, frame: k.frame });
  files.push(output);
  console.log('✓', path.relative(ROOT, output));
}
await browser.close({ silent: true });
// Contact sheet: 4 columns of 480×270 thumbnails.
const cols = 4;
const inputs = files.flatMap((f) => ['-i', f]);
const scaled = files.map((_, i) => `[${i}]scale=480:270[s${i}]`).join(';');
const layout = files.map((_, i) => `${(i % cols) * 480}_${Math.floor(i / cols) * 270}`).join('|');
execFileSync('ffmpeg', ['-v', 'error', '-y', ...inputs, '-filter_complex', `${scaled};${files.map((_, i) => `[s${i}]`).join('')}xstack=inputs=${files.length}:layout=${layout}`, path.join(out, 'contact-sheet.png')]);
console.log('✓ out/stills/contact-sheet.png');
