// Renders specific frames of the video for close inspection (one bundle, one browser, one frame at a time).
// Usage: npm run frames -- 120 450 900 [--out .scratch/frames] [--scale 0.5]
//        npm run frames -- --sheet s3 [--step 30]     every --step frames of a scene, tiled into one PNG (needs ffmpeg)
import { execFileSync } from 'node:child_process';
import fs from 'node:fs';
import path from 'node:path';
import { openBrowser, renderStill, selectComposition } from '@remotion/renderer';
import { SCENES } from '../src/timeline';
import { CHROMIUM, ROOT, arg, bundleProject } from './lib';

const out = path.join(ROOT, arg('out', '.scratch/frames')!);
const scale = Number(arg('scale', '0.5'));
const sheet = arg('sheet');
const step = Number(arg('step', '30'));
let frames = process.argv.slice(2).filter((a, i, all) => /^\d+$/.test(a) && !['--scale', '--step', '--out'].includes(all[i - 1] ?? '')).map(Number);
if (sheet) {
  const s = SCENES.find((x) => x.id === sheet);
  if (!s) throw new Error(`Unknown scene ${sheet}`);
  frames = [];
  for (let f = s.from; f < s.from + s.durationInFrames; f += step) frames.push(f);
  frames.push(s.from + s.durationInFrames - 1);
}
fs.mkdirSync(out, { recursive: true });
const serveUrl = await bundleProject();
const browser = await openBrowser('chrome', { chromiumOptions: CHROMIUM });
const composition = await selectComposition({ serveUrl, id: 'Demo', puppeteerInstance: browser });
const files: string[] = [];
for (const frame of frames) {
  const output = path.join(out, `f${String(frame).padStart(4, '0')}.png`);
  await renderStill({ chromiumOptions: CHROMIUM, puppeteerInstance: browser, composition, serveUrl, output, frame, scale });
  files.push(output);
  console.log('✓', path.relative(ROOT, output));
}
await browser.close({ silent: true });
if (sheet) {
  const cols = 4;
  const sheetOut = path.join(out, `sheet-${sheet}.png`);
  const args = files.flatMap((f) => ['-i', f]);
  const n = files.length;
  const rows = Math.ceil(n / cols);
  const layout = files.map((_, i) => `${(i % cols) === 0 ? '0' : Array.from({ length: i % cols }, () => 'w0').join('+')}_${Math.floor(i / cols) === 0 ? '0' : Array.from({ length: Math.floor(i / cols) }, () => 'h0').join('+')}`).join('|');
  execFileSync('ffmpeg', ['-v', 'error', '-y', ...args, '-filter_complex', `xstack=inputs=${n}:layout=${layout}:fill=black${n < cols * rows ? '' : ''}`, sheetOut]);
  console.log('sheet', path.relative(ROOT, sheetOut));
}
