// Verifies every scene boundary is continuous: compares the last frame of each scene with the first of the next
// (quarter resolution) and reports how many pixels changed, next to a typical in-scene step for scale.
// Usage: npm run cut-check [-- s2]   (optionally only boundaries into the named scene)
import { renderFrames, selectComposition } from '@remotion/renderer';
import { PNG } from 'pngjs';
import { SCENES } from '../src/timeline';
import { bundleProject, CHROMIUM , CONCURRENCY } from './lib';

const only = process.argv[2];
const serveUrl = await bundleProject();
const composition = await selectComposition({ serveUrl, id: 'Demo' });
const changed = (a: Buffer, b: Buffer) => {
  let n = 0;
  for (let i = 0; i < a.length; i += 4) if (Math.abs(a[i] - b[i]) + Math.abs(a[i + 1] - b[i + 1]) + Math.abs(a[i + 2] - b[i + 2]) > 30) n++;
  return n;
};
const grab = async (frames: number[]) => {
  const out = new Map<number, Buffer>();
  for (const f of frames) {
    await renderFrames({ chromiumOptions: CHROMIUM, concurrency: CONCURRENCY,
      composition, serveUrl, inputProps: {}, outputDir: null, imageFormat: 'png', scale: 0.25, frameRange: [f, f],
      onStart: () => undefined, onFrameUpdate: () => undefined,
      onFrameBuffer: (buf, frame) => { out.set(frame, PNG.sync.read(buf).data); },
    });
  }
  return out;
};
const total = 480 * 270;
for (const s of SCENES.slice(1)) {
  if (only && s.id !== only) continue;
  const b = s.from;
  const px = await grab([b - 2, b - 1, b, b + 1]);
  const before = changed(px.get(b - 2)!, px.get(b - 1)!);
  const cut = changed(px.get(b - 1)!, px.get(b)!);
  const after = changed(px.get(b)!, px.get(b + 1)!);
  const ratio = cut / Math.max(1, before, after);
  const verdict = cut < total * 0.02 || ratio < 3 ? 'continuous' : 'JUMP';
  console.log(`${verdict.padEnd(11)} ${s.id} @${b}: cut ${cut} px · neighbours ${before}/${after} px`);
}
