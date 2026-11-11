// The laptop scene's title and screen (the screen grows into the decoding scene's frame).
import { TYPE } from '../../brand/tokens';

export const S7_TITLE = { x: 160, y: 118, size: TYPE.title } as const;
export const SCREEN = { x: 190, y: 250, w: 680, h: 400, r: 18 } as const;

/** The top edge of the laptop's base: S5's teaching curve flattens into it. */
export const LAPTOP_BASE = { x0: SCREEN.x - 80, x1: SCREEN.x + SCREEN.w + 80, y: SCREEN.y + SCREEN.h + 34 } as const;
