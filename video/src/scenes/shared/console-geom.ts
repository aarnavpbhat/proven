// Geometry of the rebuilt review console (proven/web/index.html, scaled up so nothing is under 28 px).
// Shared by S2 (which carries the first sentence into the explanation pane) and S3 (the walkthrough).
// Content stays above y 940 (subtitle band) and right of x 544 below y 746 (face-cam corner).

export const FRAME = { x: 60, y: 30, w: 1800, h: 1020, bar: 52 } as const;
export const SIDEBAR = { x: FRAME.x, w: 280 } as const;
export const MAIN = { x: SIDEBAR.x + SIDEBAR.w + 44, right: FRAME.x + FRAME.w - 44 } as const; // 384 … 1816
export const TOPBAR = { y: FRAME.y + FRAME.bar, h: 64 } as const; // 82 … 146
export const HEAD = { y: 168 } as const;
export const COVERAGE = { y: 284, bar: 452 } as const;
export const SPLIT = { y: 478, yFolded: 300, bottom: 940 } as const;
export const LIST = { x: MAIN.x, w: 600 } as const; // 384 … 984
export const DETAIL = { x: LIST.x + LIST.w + 24, w: MAIN.right - (LIST.x + LIST.w + 24) } as const; // 1008 … 1816
export const PANE_PAD = 32;

// The explanation pane before Verify spans the whole split. Its sentences start right of the face-cam column
// (x ≥ 552) and their claim tags sit at the right edge, so nothing in the lower rows enters KEEP_CLEAR.
export const EXPL = { x: MAIN.x, w: MAIN.right - MAIN.x, top: SPLIT.y + 76, size: 28, line: 44, tagX: MAIN.right - 72 } as const;
export const EXPL_TEXT_X = 552;

/** Where S2 drops the carried sentence: the first line of the explanation pane. */
export const LINE1 = { x: EXPL_TEXT_X, y: EXPL.top, size: EXPL.size } as const;
