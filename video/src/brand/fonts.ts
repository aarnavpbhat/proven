import { loadFont as loadSans } from '@remotion/google-fonts/Inter';
import { loadFont as loadMono } from '@remotion/google-fonts/IBMPlexMono';

// Loaded once at module scope; rendering blocks until the fonts are ready.
const s = loadSans('normal', { weights: ['400', '500'], subsets: ['latin'] });
const m = loadMono('normal', { weights: ['400', '500'], subsets: ['latin'] });

export const sans = s.fontFamily;
export const mono = m.fontFamily;


// Text measurement must wait for this, or measureText caches fallback-font widths.
export const fontsReady: Promise<unknown> = Promise.all([s, m].map((f) => f.waitUntilDone()));
