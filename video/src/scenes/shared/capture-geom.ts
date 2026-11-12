// Camera focus rects on the console captures (CSS px of the capture viewport, see src/data/capture.ts), shared by
// the walkthrough scenes so a scene can start exactly where the previous one ended. Read off the captures with
// .scratch/crop.sh; the camera fits each rect into STAGE (CaptureView.tsx).
import type { Rect } from '../../components/CaptureView';

export const FOCUS = {
  /** The console's top 16:9 region. */
  wide: { x: 0, y: 0, w: 1440, h: 810 },
  /** The same width, scrolled down: the lower part of a long detail panel. */
  low: { x: 0, y: 640, w: 1440, h: 810 },
  lumenCoverage: { x: 250, y: 140, w: 1172, h: 130 },
  brightNoteWide: { x: 250, y: 150, w: 700, h: 200 },
  lumenEditor: { x: 257, y: 296, w: 514, h: 330 },
  lumenDetail: { x: 806, y: 350, w: 600, h: 400 },
  lumenFindings: { x: 810, y: 895, w: 600, h: 250 },
  brightExtractor: { x: 880, y: 66, w: 540, h: 112 },
  brightNote: { x: 250, y: 168, w: 560, h: 60 },
  brightRow: { x: 250, y: 400, w: 530, h: 145 },
  brightSearched: { x: 810, y: 690, w: 600, h: 130 },
  brightFindings: { x: 810, y: 440, w: 600, h: 330 },
  queueItem: { x: 286, y: 270, w: 720, h: 100 },
  teachFields: { x: 815, y: 1095, w: 600, h: 190 },
  gate: { x: 826, y: 1186, w: 560, h: 100 },
  confirm: { x: 826, y: 1190, w: 560, h: 140 },
  record: { x: 870, y: 900, w: 540, h: 100 },
  passRow: { x: 250, y: 495, w: 530, h: 170 },
  learnedTab: { x: 0, y: 62, w: 560, h: 170 },
  cobaltHeader: { x: 250, y: 58, w: 580, h: 90 },
  cobaltExtractor: { x: 880, y: 60, w: 540, h: 110 },
  cobaltDetail: { x: 806, y: 345, w: 600, h: 400 },
  cobaltSearched: { x: 810, y: 640, w: 600, h: 110 },
} as const satisfies Record<string, Rect>;
