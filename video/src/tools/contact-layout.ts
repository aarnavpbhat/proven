// Contact-sheet geometry and frame list, kept free of React and fonts so scripts/contact-sheet.ts can import it.
import { SCENES, TOTAL_FRAMES, type SceneId } from '../timeline';

export interface SheetProps extends Record<string, unknown> {
  scene: SceneId | 'all';
  step: number;
}

export const COLS = 6;
export const CELL_W = 320;
export const CELL_H = 180;
export const LABEL = 30;
export const GAP = 16;
export const HEADER = 70;

export const framesFor = ({ scene, step }: SheetProps): number[] => {
  const s = scene === 'all' ? { from: 0, durationInFrames: TOTAL_FRAMES } : SCENES.find((x) => x.id === scene)!;
  const out: number[] = [];
  for (let f = s.from; f < s.from + s.durationInFrames; f += step) out.push(f);
  out.push(s.from + s.durationInFrames - 1);
  return out;
};

export const CELL = { w: CELL_W, h: CELL_H } as const;
