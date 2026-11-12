// Geometry of the architecture diagram (S4), shared with S3 (which carries the confirmed lesson into its node) and
// S5 (which carries the FAIL and PASS chips out of the verdict node).

export interface Box {
  x: number;
  y: number;
  w: number;
  h: number;
}

export const NODES = {
  explanation: { x: 136, y: 226, w: 354, h: 100 },
  chart: { x: 136, y: 356, w: 354, h: 100 },
  proposer: { x: 550, y: 226, w: 330, h: 230 },
  admission: { x: 970, y: 276, w: 270, h: 130 },
  ledger: { x: 1300, y: 112, w: 280, h: 96 },
  checker: { x: 1300, y: 276, w: 280, h: 130 },
  verdicts: { x: 1630, y: 226, w: 200, h: 230 },
  reviewer: { x: 1490, y: 640, w: 330, h: 150 },
  gate: { x: 1200, y: 640, w: 260, h: 150 },
  lessons: { x: 580, y: 620, w: 580, h: 170 },
} as const satisfies Record<string, Box>;

export type NodeId = keyof typeof NODES;

export const BOUNDARY_X = 920;

/** Where the confirmed-lesson pill sits when S4 begins (inside the lessons node). Two lines. */
export const LESSON_PILL = { x: NODES.lessons.x + 24, y: NODES.lessons.y + 66, w: 532 } as const;

/** The verdict chips inside the verdicts node, top to bottom. */
export const VERDICT_CHIPS = ['PASS', 'FAIL', 'REVIEW'] as const;
export const verdictChipPos = (i: number): { x: number; y: number } => ({ x: NODES.verdicts.x + 16, y: NODES.verdicts.y + 34 + i * 62 });
