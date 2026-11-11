// Recorded takes, one per VO line (src/timeline.ts). Nothing here is required: a missing file is skipped, and the
// video renders silent with subtitles. See docs/recording-guide.md for what to record and where files go.
//
//   public/facecam/line-NN.mp4   a face-cam take (video + its own audio). Shown picture-in-picture, carries the voice.
//   public/voice/line-NN.wav     an audio-only take. Used when there is no face-cam file for the line.
//   public/audio/music.wav       optional music bed, ducked under the voice.
//
// `lead` is how many frames of room tone the file has before the first word (30 frames = 1 s). The file starts at
// VO.from − lead, so the first word lands on the line's beat without retiming any scene. Set it after recording
// (docs/recording-guide.md, step 5). `speaker` only labels the slot in the studio preview.
import { VO } from '../timeline';

export interface Take {
  line: number;
  speaker: 1 | 2 | 3;
  lead: number;
}

// Hook and close: speaker 1 · walkthrough: speaker 2 (Lumen, Brightfield) and 3 (gate, next close) · loop, proof, next: 1.
const SPEAKERS: Record<number, 1 | 2 | 3> = { 1: 1, 2: 2, 3: 2, 4: 2, 5: 2, 6: 2, 7: 2, 8: 3, 9: 3, 10: 3, 11: 1, 12: 1, 13: 1, 14: 1, 15: 1 };

export const TAKES: Take[] = VO.map((l) => ({ line: l.n, speaker: SPEAKERS[l.n] ?? 1, lead: 8 }));

export const pad2 = (n: number): string => String(n).padStart(2, '0');
export const facecamFile = (line: number): string => `facecam/line-${pad2(line)}.mp4`;
export const voiceFile = (line: number): string => `voice/line-${pad2(line)}.wav`;
export const MUSIC_FILE = 'audio/music.wav';
