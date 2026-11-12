// Frame-driven motion helpers (copied from the v2 editor). Every curve comes from tokens.ts; nothing here reads the clock.
import { Easing, interpolate, spring } from 'remotion';
import { EASE, SPRING, STAGGER } from '../brand/tokens';

type Bezier = readonly [number, number, number, number];
const bz = (p: Bezier) => Easing.bezier(p[0], p[1], p[2], p[3]);

export const ease = {
  standard: bz(EASE.standard),
  enter: bz(EASE.enter),
  exit: bz(EASE.exit),
} as const;
export type Curve = keyof typeof ease;

const CLAMP = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;

/** 0→1 over [start, start+duration] with the given curve, clamped. */
export const progress = (frame: number, start: number, duration: number, curve: Curve = 'standard'): number =>
  interpolate(frame, [start, start + duration], [0, 1], { ...CLAMP, easing: ease[curve] });

export const enter = (frame: number, start: number, duration: number) => progress(frame, start, duration, 'enter');
export const exit = (frame: number, start: number, duration: number) => progress(frame, start, duration, 'exit');

/** Spring from a start frame using a named preset. */
export const springAt = (frame: number, fps: number, start: number, preset: keyof typeof SPRING): number =>
  spring({ frame: frame - start, fps, config: SPRING[preset] });

export const mix = (a: number, b: number, t: number): number => a + (b - a) * t;

/** Stroke draw-on for any SVG shape. Spread onto the element; uses pathLength=1 so no measuring is needed. */
export const drawOn = (t: number) => ({
  pathLength: 1,
  strokeDasharray: '1 1',
  strokeDashoffset: 1 - Math.min(1, Math.max(0, t)),
  strokeOpacity: t <= 0 ? 0 : undefined, // a round cap would otherwise show a dot before drawing starts
});

/** Integer count from→to landing exactly at `end` (put `end` on a beat). */
export const countTo = (frame: number, start: number, end: number, from: number, to: number): number =>
  Math.round(interpolate(frame, [start, end], [from, to], { ...CLAMP, easing: ease.standard }));

/** Start offset for item i of a staggered group (2–4 frames per item). */
export const stagger = (i: number, step: keyof typeof STAGGER = 'base'): number => i * STAGGER[step];

/** Scene camera: slow push-in plus optional pan, as an SVG transform for the scene's root <g>. */
export const camera = ({
  frame,
  duration,
  pushIn = 0.02,
  pan = [0, 0],
  origin = [960, 540],
}: {
  frame: number;
  duration: number;
  pushIn?: number;
  pan?: [number, number];
  origin?: [number, number];
}): string => {
  const t = progress(frame, 0, duration, 'standard');
  const s = 1 + pushIn * t;
  const [ox, oy] = origin;
  return `translate(${pan[0] * t} ${pan[1] * t}) translate(${ox} ${oy}) scale(${s}) translate(${-ox} ${-oy})`;
};

/**
 * Entrance for text and UI: rises `dist` px into place while fading up, on the enter curve. No mask, so a word is
 * never cropped mid-move. Spread onto the element's style.
 */
export const rise = (frame: number, start: number, duration = 12, dist = 24): { opacity: number; transform: string } => {
  const t = enter(frame, start, duration);
  return { opacity: t, transform: `translateY(${(1 - t) * dist}px)` };
};

/** Exit for text and UI: lifts `dist` px while fading out, on the exit curve. */
export const lift = (frame: number, start: number, duration = 8, dist = 16): { opacity: number; transform: string } => {
  const t = exit(frame, start, duration);
  return { opacity: 1 - t, transform: `translateY(${-t * dist}px)` };
};

/** Linear blend of two 3-vectors (camera poses). */
export const mix3 = (a: readonly [number, number, number], b: readonly [number, number, number], t: number): [number, number, number] => [
  mix(a[0], b[0], t),
  mix(a[1], b[1], t),
  mix(a[2], b[2], t),
];
