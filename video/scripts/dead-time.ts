// Finds static stretches: renders every 3rd frame at quarter resolution and diffs consecutive samples.
// A sample pair is "static" when fewer than MIN_CHANGED pixels moved by more than PIXEL_DELTA.
// Any static run longer than 36 frames fails, except the final hold at the very end of the video.
// Usage: npm run dead-time -- [--scene s6]
import { renderFrames, selectComposition } from '@remotion/renderer';
import { PNG } from 'pngjs';
import { FINAL_HOLD, SCENES, TOTAL_FRAMES } from '../src/timeline';
import { arg, bundleProject, CHROMIUM , CONCURRENCY } from './lib';

const STEP = 3;
const MAX_STATIC = 36;
const PIXEL_DELTA = 10; // 0–255 per channel
const MIN_CHANGED = 40; // pixels at 480×270

const only = arg('scene');
const range: [number, number] = only
  ? (() => {
      const s = SCENES.find((x) => x.id === only);
      if (!s) throw new Error(`Unknown scene ${only}`);
      return [s.from, s.from + s.durationInFrames - 1];
    })()
  : [0, TOTAL_FRAMES - 1];

const serveUrl = await bundleProject();
const composition = await selectComposition({ serveUrl, id: 'Demo' });
const samples = new Map<number, Buffer>();
await renderFrames({ chromiumOptions: CHROMIUM, concurrency: CONCURRENCY,
  composition,
  serveUrl,
  inputProps: {},
  outputDir: null,
  imageFormat: 'png',
  scale: 0.25,
  everyNthFrame: STEP,
  frameRange: range,
  onStart: () => undefined,
  onFrameUpdate: () => undefined,
  onFrameBuffer: (buf, frame) => {
    samples.set(frame, PNG.sync.read(buf).data);
  },
});

const frames = [...samples.keys()].sort((a, b) => a - b);
const changed = (a: Buffer, b: Buffer) => {
  let n = 0;
  for (let i = 0; i < a.length; i += 4) {
    if (Math.abs(a[i] - b[i]) > PIXEL_DELTA || Math.abs(a[i + 1] - b[i + 1]) > PIXEL_DELTA || Math.abs(a[i + 2] - b[i + 2]) > PIXEL_DELTA) n++;
  }
  return n;
};

const runs: { start: number; end: number }[] = [];
let runStart: number | null = null;
for (let i = 1; i < frames.length; i++) {
  const isStatic = changed(samples.get(frames[i - 1])!, samples.get(frames[i])!) < MIN_CHANGED;
  if (isStatic && runStart === null) runStart = frames[i - 1];
  if (!isStatic && runStart !== null) {
    runs.push({ start: runStart, end: frames[i - 1] });
    runStart = null;
  }
}
if (runStart !== null) runs.push({ start: runStart, end: frames[frames.length - 1] });

const sceneOf = (f: number) => SCENES.find((s) => f >= s.from && f < s.from + s.durationInFrames)?.id ?? '?';
const isFinalHold = (r: { start: number; end: number }) => r.end >= TOTAL_FRAMES - STEP && r.end - r.start >= FINAL_HOLD - STEP;
let failures = 0;
for (const r of runs) {
  const len = r.end - r.start;
  const tag = len > MAX_STATIC ? (isFinalHold(r) ? 'final hold (allowed)' : 'FAIL') : 'ok';
  if (tag === 'FAIL') failures++;
  if (len >= 15) console.log(`${tag.padEnd(20)} ${sceneOf(r.start)} frames ${r.start}–${r.end} (${len} static)`);
}
console.log(failures ? `\n${failures} static stretch(es) over ${MAX_STATIC} frames.` : `\nNo static stretch over ${MAX_STATIC} frames (range ${range[0]}–${range[1]}).`);
process.exitCode = failures ? 1 : 0;
