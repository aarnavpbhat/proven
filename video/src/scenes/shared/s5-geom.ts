// Where S5 shows the two kill-criteria chips (carried from S4's verdict node). `size` is the on-screen chip text size.
export const S5_CHIPS = {
  fail: { x: 160, y: 236, size: 44 },
  pass: { x: 160, y: 520, size: 44 },
} as const;

// Where S6 keeps the two chips as its kill-criteria legend (top right), at eyebrow size.
export const S6_CHIPS = {
  fail: { x: 1380, y: 104, size: 28 },
  pass: { x: 1590, y: 104, size: 28 },
} as const;
