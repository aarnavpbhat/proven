// Camera state as world→screen: screen = s * world + (tx, ty). Scenes compose these per frame.
import { mix } from './anim';

export interface Cam {
  s: number;
  tx: number;
  ty: number;
}

export const IDENTITY: Cam = { s: 1, tx: 0, ty: 0 };

/** Zoom by `s` keeping world point (cx, cy) at screen point (sx, sy) (defaults to the same point). */
export const zoomAt = (s: number, cx: number, cy: number, sx = cx, sy = cy): Cam => ({ s, tx: sx - s * cx, ty: sy - s * cy });

export const lerpCam = (a: Cam, b: Cam, t: number): Cam => ({ s: mix(a.s, b.s, t), tx: mix(a.tx, b.tx, t), ty: mix(a.ty, b.ty, t) });

export const camTransform = (c: Cam): string => `translate(${c.tx} ${c.ty}) scale(${c.s})`;

export const toScreen = (c: Cam, x: number, y: number) => ({ x: c.tx + c.s * x, y: c.ty + c.s * y });
