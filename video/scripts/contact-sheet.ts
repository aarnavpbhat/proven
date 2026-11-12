// Renders a contact sheet (a thumbnail every --step frames, default one beat) for one scene or all of them.
// Usage: npm run contact-sheet -- --scene s6 [--step 15]    (omit --scene for every scene, --scene all for the whole video on one sheet)
// Thumbnails are rendered from the video into public/contact-frames/ first; the sheet composition then tiles them.
import fs from 'node:fs';
import path from 'node:path';
import { openBrowser, renderStill, selectComposition } from '@remotion/renderer';
import { CANVAS } from '../src/brand/tokens';
import { CELL, framesFor, type SheetProps } from '../src/tools/contact-layout';
import { SCENES, type SceneId } from '../src/timeline';
import { ROOT, arg, bundleProject, CHROMIUM } from './lib';

const step = Number(arg('step', '15'));
const only = arg('scene');
const targets = (only ? [only] : SCENES.map((s) => s.id)) as SheetProps['scene'][];

let serveUrl = await bundleProject();
// One browser per batch of thumbnails: launching one per still would dominate the run time, but a single browser
// rendering many 3D frames in a row eventually stops answering (GPU contexts pile up). Recycle it, retry once.
const BATCH = 10;
let browser = await openBrowser('chrome', { chromiumOptions: CHROMIUM });
let used = 0;
const recycle = async () => {
  await browser.close({ silent: true }).catch(() => undefined);
  browser = await openBrowser('chrome', { chromiumOptions: CHROMIUM });
  used = 0;
};
const demo = await selectComposition({ serveUrl, id: 'Demo', chromiumOptions: CHROMIUM, puppeteerInstance: browser });
for (const scene of targets) {
  const dir = path.join(ROOT, 'public/contact-frames', scene);
  fs.rmSync(dir, { recursive: true, force: true });
  fs.mkdirSync(dir, { recursive: true });
  for (const frame of framesFor({ scene, step })) {
    if (used >= BATCH) await recycle();
    const still = () =>
      renderStill({
        chromiumOptions: CHROMIUM,
        puppeteerInstance: browser,
        composition: demo,
        serveUrl,
        frame,
        imageFormat: 'jpeg',
        jpegQuality: 85,
        scale: CELL.w / CANVAS.width,
        output: path.join(dir, `f${frame}.jpeg`),
      });
    await still().catch(async () => {
      await recycle();
      await still();
    });
    used++;
  }
}
// Re-bundle so the new thumbnails are in the bundle's public folder.
serveUrl = await bundleProject();
for (const scene of targets) {
  const inputProps = { scene: scene as SceneId | 'all', step };
  const composition = await selectComposition({
    serveUrl,
    id: 'ContactSheet',
    inputProps,
    chromiumOptions: CHROMIUM,
  });
  const output = path.join(ROOT, 'out/contact', `${scene}.png`);
  await renderStill({
    chromiumOptions: CHROMIUM,
    composition,
    serveUrl,
    output,
    inputProps,
    frame: 0,
  });
  console.log('✓', path.relative(ROOT, output));
}
await browser.close({ silent: true });
