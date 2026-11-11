// Geometry shared by S1 (the hero sentence at headline size) and S2 (the same words, scaled into the proposal's
// quote field). Pure functions of the fonts; call only under <FontGate>.
import { COLUMN, TYPE } from '../../brand/tokens';
import { LUMEN } from '../../data/cases';
import { layoutWords, type WordBox } from '../../lib/svg';

export const HERO_SIZE = TYPE.headline; // 120
export const HERO_LH = 1.45;
export const HERO_TOP = 180; // top of the first line box
export const HERO_X = COLUMN.x;

/** The parts of the sentence the proposer reads out, by word index range [from, to). */
export const PARTS = {
  account: { from: 0, to: 2, label: 'Account' }, // "Legal costs"
  amount: { from: 3, to: 4, label: 'Amount' }, // "$90K"
  reason: { from: 6, to: 11, label: 'Reason' }, // "our Series B funding round."
} as const;
export type PartId = keyof typeof PARTS;

export const heroWords = (): WordBox[] =>
  layoutWords(
    LUMEN.c1.quote.split(' ').map((text) => ({ text })),
    'sans',
    HERO_SIZE,
    HERO_X,
    HERO_TOP,
    // Break after "$90K" and after "Series B": three lines that keep the reason together on lines 2–3.
    { maxWidth: 1480, lineHeight: HERO_LH },
  );

/** Line boxes of a word range: one segment per line, [x0, x1, top]. */
export const segments = (words: WordBox[], from: number, to: number): { x0: number; x1: number; top: number }[] => {
  const ws = words.slice(from, to);
  const lines = [...new Set(ws.map((w) => w.line))];
  return lines.map((l) => {
    const on = ws.filter((w) => w.line === l);
    const last = on[on.length - 1];
    // Trailing period is not part of the reason's underline.
    const trim = last.text.endsWith('.') ? last.width * (1 / last.text.length) : 0;
    return { x0: on[0].x, x1: last.x + last.width - trim, top: on[0].y };
  });
};

/** Bottom of the sentence block. */
export const heroBottom = (words: WordBox[]): number => Math.max(...words.map((w) => w.y)) + HERO_SIZE * HERO_LH;
