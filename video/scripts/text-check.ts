// Text check: overlapping text, text cut by the frame or by a covering card, text under 28 px, text in the face-cam
// corner, scene text under a subtitle. Renders with inputProps { audit: true } so src/tools/TextAudit.tsx measures
// the live DOM. (Adapted from the v2 editor.)
// Usage:
//   npm run text-check                               every 5th frame of the whole video
//   npm run text-check -- --scene s3 [--every 2]     one scene
//   npm run text-check -- --from 600 --to 900 [--every 1]
// Exits 1 if anything is flagged (face-cam warnings only count when SHOW_FACECAM is on).
import { renderFrames, selectComposition } from '@remotion/renderer';
import path from 'node:path';
import { SHOW_FACECAM } from '../src/brand/tokens';
import { SCENES } from '../src/timeline';
import type { TextIssue } from '../src/tools/TextAudit';
import { CHROMIUM, CONCURRENCY, ROOT, arg, bundleProject } from './lib';

const inputProps = { audit: true };
const serveUrl = await bundleProject();
const results = new Map<number, TextIssue[]>();

const composition = await selectComposition({ serveUrl, id: 'Demo', inputProps, chromiumOptions: CHROMIUM });
const sceneId = arg('scene');
const spec = sceneId ? SCENES.find((s) => s.id === sceneId) : undefined;
if (sceneId && !spec) throw new Error(`Unknown scene ${sceneId}`);
const from = Number(arg('from', String(spec ? spec.from : 0)));
const to = Number(arg('to', String(spec ? spec.from + spec.durationInFrames - 1 : composition.durationInFrames - 1)));
const every = Number(arg('every', '5'));

await renderFrames({
  chromiumOptions: CHROMIUM,
  concurrency: CONCURRENCY,
  composition,
  serveUrl,
  inputProps,
  outputDir: path.join(ROOT, '.scratch/text-check-frames'),
  imageFormat: 'jpeg',
  frameRange: [from, to],
  everyNthFrame: every,
  scale: 0.25,
  onStart: () => undefined,
  onFrameUpdate: () => undefined,
  onBrowserLog: (log) => {
    if (!log.text.startsWith('TEXT_AUDIT ')) return;
    const { frame, issues } = JSON.parse(log.text.slice('TEXT_AUDIT '.length)) as { frame: number; issues: TextIssue[] };
    results.set(frame, issues); // last measurement of a frame wins
  },
});

let failures = 0;
const sceneOf = (f: number): string => SCENES.find((s) => f >= s.from && f < s.from + s.durationInFrames)?.id ?? '?';
for (const [frame, issues] of [...results.entries()].sort((a, b) => a[0] - b[0])) {
  const counted = issues.filter((i) => i.kind !== 'facecam' || SHOW_FACECAM);
  failures += counted.length;
  if (!counted.length) continue;
  console.log(`✗ f${frame} (${sceneOf(frame)}) — ${counted.length} issue(s)`);
  for (const i of counted) console.log(`    ${i.kind.padEnd(8)} "${i.text}"${i.other ? ` × "${i.other}"` : ''}  (${i.detail})`);
}
console.log(failures ? `\n${failures} text issue(s) in ${results.size} frame(s).` : `\nNo text issues in ${results.size} frame(s) (${from}–${to}, every ${every}).`);
process.exit(failures ? 1 : 0);
