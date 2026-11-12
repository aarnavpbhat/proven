// Text layout helpers. Only call measure() under <FontGate>, after fonts have loaded.
// Figures are proportional in running text and tabular (`TABULAR`) in columns that must line up. Not tabular
// everywhere: Inter's tnum set also widens the hyphen, which spaces out "month-end" and "in-store".
import { measureText } from '@remotion/layout-utils';
import type { CSSProperties } from 'react';
import { COLORS, TRACKING, TYPE } from '../brand/tokens';
import { mono, sans } from '../brand/fonts';

export const FAMILY = { sans, mono } as const;
export type Face = keyof typeof FAMILY;

/** Tracking for a size: tight for display type, slight for body, none for mono. */
export const trackingFor = (face: Face, size: number): number =>
  face === 'mono' ? 0 : size >= TYPE.headline ? TRACKING.display : TRACKING.body;

export const measure = (text: string, face: Face, size: number, weight: number | string = 400, letterSpacingEm = trackingFor(face, size)): number =>
  measureText({
    text,
    fontFamily: FAMILY[face],
    fontSize: size,
    fontWeight: weight,
    letterSpacing: letterSpacingEm ? `${letterSpacingEm}em` : undefined,
    validateFontIsLoaded: true,
  }).width;

/** Tabular figures, for amount and date columns. Spread after css(). */
export const TABULAR: CSSProperties = { fontVariantNumeric: 'tabular-nums' };

/** CSS for an HTML text element. */
export const css = (face: Face, size: number, color: string = COLORS.ink, weight: number = 400): CSSProperties => ({
  fontFamily: FAMILY[face],
  fontSize: size,
  fontWeight: weight,
  color,
  letterSpacing: `${trackingFor(face, size)}em`,
  whiteSpace: 'pre',
});

/** Props for an SVG <text>. */
export const textStyle = (face: Face, size: number, fill: string = COLORS.ink, weight: number = 400) => ({
  fontFamily: FAMILY[face],
  fontSize: size,
  fontWeight: weight,
  fill,
  letterSpacing: `${trackingFor(face, size)}em`,
});

export interface WordBox {
  text: string;
  key?: string;
  x: number;
  y: number; // baseline
  width: number;
  line: number;
}

/**
 * Lays out words left-aligned from (x, y baseline). `\n` as a word forces a break.
 * Words with a `key` can be looked up afterwards (e.g. to highlight "$60K").
 */
export const layoutWords = (
  words: { text: string; key?: string }[],
  face: Face,
  size: number,
  x: number,
  y: number,
  opts: { maxWidth?: number; lineHeight?: number; weight?: number } = {},
): WordBox[] => {
  const space = measure(' ', face, size, opts.weight);
  const lh = (opts.lineHeight ?? 1.0) * size;
  const out: WordBox[] = [];
  let cx = x;
  let line = 0;
  for (const w of words) {
    if (w.text === '\n') {
      cx = x;
      line++;
      continue;
    }
    const width = measure(w.text, face, size, opts.weight);
    if (opts.maxWidth && cx > x && cx + width > x + opts.maxWidth) {
      cx = x;
      line++;
    }
    out.push({ text: w.text, key: w.key, x: cx, y: y + line * lh, width, line });
    cx += width + space;
  }
  return out;
};

export const box = (boxes: WordBox[], key: string): WordBox => {
  const b = boxes.find((w) => w.key === key);
  if (!b) throw new Error(`No word with key ${key}`);
  return b;
};

/** "2026-10-22" → "Oct 22" */
export const fmtDate = (iso: string): string => {
  const [, m, d] = iso.split('-').map(Number);
  const months = ['Jan', 'Feb', 'Mar', 'Apr', 'May', 'Jun', 'Jul', 'Aug', 'Sep', 'Oct', 'Nov', 'Dec'];
  return `${months[m - 1]} ${String(d).padStart(2, '0')}`;
};

/** Split a sentence into words, tagging some with keys by exact match. */
export const tagWords = (text: string, keys: Record<string, string> = {}): { text: string; key?: string }[] =>
  text.split(' ').map((t) => ({ text: t, key: keys[t] }));
