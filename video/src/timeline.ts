// Single source of truth for timing. Scenes and components import from here; no bare scene ranges elsewhere.
// The narration in docs/script.md is the same text as VO below (scripts/check-data.ts asserts it).

export const FPS = 30;
export const BEAT = 15; // 120 BPM at 30 fps
export const BAR = 4 * BEAT;
export const TOTAL_FRAMES = 3540; // 118 s
export const FINAL_HOLD = 3 * BEAT; // minimum static hold at the very end

export type SceneId = 's1' | 's2' | 's3' | 's4' | 's5' | 's6' | 's7' | 's8' | 's9';

export interface SceneSpec {
  id: SceneId;
  from: number;
  durationInFrames: number;
  label: string;
}

// s2–s5 are the product walkthrough: real captures of the console (public/capture, scripts/capture-console.ts).
export const SCENES: SceneSpec[] = [
  { id: 's1', from: 0, durationInFrames: 240, label: 'Hook' },
  { id: 's2', from: 240, durationInFrames: 720, label: 'Walkthrough: paste and verify' },
  { id: 's3', from: 960, durationInFrames: 510, label: 'Walkthrough: a claim waits for a person' },
  { id: 's4', from: 1470, durationInFrames: 510, label: 'Walkthrough: safety gate, confirm once' },
  { id: 's5', from: 1980, durationInFrames: 345, label: 'Walkthrough: next close, rules alone' },
  { id: 's6', from: 2325, durationInFrames: 330, label: 'Architecture loop' },
  { id: 's7', from: 2655, durationInFrames: 600, label: 'Proof' },
  { id: 's8', from: 3255, durationInFrames: 165, label: 'Path forward' },
  { id: 's9', from: 3420, durationInFrames: 120, label: 'Close' },
];

/** The scene whose words are on the end card, so it gets no subtitle. */
export const END_CARD_SCENE: SceneId = 's9';

// Narration, one entry per recorded take. `from` is the frame the take's first word should land on (a beat);
// `to` is the end of its slot: a take must finish before `to` (scripts/check-data.ts reads the WAV length when a
// take exists). Subtitles split `text` at sentence and clause breaks (" | " forces a break).
export interface VoLine {
  n: number;
  scene: SceneId;
  from: number;
  to: number;
  text: string;
  /** Words still to be decided (pending numbers). The line must not be recorded until this is empty. */
  pending?: string;
}

export const VO: VoLine[] = [
  { n: 1, scene: 's1', from: 15, to: 225, text: 'Every month-end close, finance teams explain why each number moved. | Proven checks those explanations against the ledger.' },
  { n: 2, scene: 's2', from: 255, to: 375, text: "Paste the month's commentary and press Verify." },
  { n: 3, scene: 's2', from: 390, to: 540, text: 'Each claim gets a verdict, | and Coverage shows how much was checked.' },
  { n: 4, scene: 's2', from: 540, to: 720, text: 'Legal says ninety thousand; | the ledger shows about forty-five.' },
  { n: 5, scene: 's2', from: 735, to: 945, text: 'The evidence shows why: | a forty-five-thousand-dollar Series B invoice | was booked to Marketing.' },
  { n: 6, scene: 's3', from: 975, to: 1200, text: 'Here a language model proposes the claims. | It sees the text and chart of accounts, never a transaction.' },
  { n: 7, scene: 's3', from: 1215, to: 1455, text: "Its word, campaign, found the cause. | But only the model's word supports it, | so the claim waits for a person." },
  { n: 8, scene: 's4', from: 1485, to: 1725, text: 'The safety gate replays the lesson against explanations with known answers: | no wrong one passes, and no right one fails.' },
  { n: 9, scene: 's4', from: 1740, to: 1965, text: 'The reviewer checks the two transactions and confirms it once. | The claim passes.' },
  { n: 10, scene: 's5', from: 1995, to: 2310, text: 'On the next close, at another company, the rules run alone. | The same reason passes on the learned word. | No model ran; nothing left the machine.' },
  { n: 11, scene: 's6', from: 2340, to: 2655, text: 'The model only proposes; its reply has no verdict field. | Deterministic code decides from the ledger, | and each confirmed lesson moves work from people to rules.' },
  { n: 12, scene: 's7', from: 2670, to: 2985, text: 'On every benchmark, every wrong explanation is blocked, | and no correct one is rejected. | On eleven unseen companies, with Sonnet proposing, | almost eighty-two percent are decided.' },
  { n: 13, scene: 's7', from: 3000, to: 3240, text: 'Then we froze the checker, wrote thirteen new companies, and scored once: | all four hundred twenty-nine wrong explanations were blocked.' },
  { n: 14, scene: 's8', from: 3270, to: 3405, text: 'Next: a local open-weight proposer, | so no sentence leaves the building.' },
  { n: 15, scene: 's9', from: 3435, to: 3510, text: 'The model proposes. | The ledger decides.' },
];

export const scene = (id: SceneId): SceneSpec => {
  const s = SCENES.find((x) => x.id === id);
  if (!s) throw new Error(`Unknown scene ${id}`);
  return s;
};

export const beats = (n: number): number => n * BEAT;
export const bars = (n: number): number => n * BAR;

/** Scenes contiguous, on beats, summing to TOTAL_FRAMES; VO lines inside their scene, on beats, in order, not overlapping. */
export const validateTimeline = (scenes: SceneSpec[] = SCENES, vo: VoLine[] = VO): string[] => {
  const errors: string[] = [];
  let cursor = 0;
  for (const s of scenes) {
    if (s.from !== cursor) errors.push(`${s.id} starts at ${s.from}, expected ${cursor} (gap or overlap)`);
    if (s.from % BEAT !== 0) errors.push(`${s.id} start ${s.from} is not on a beat`);
    if (s.durationInFrames % BEAT !== 0) errors.push(`${s.id} duration ${s.durationInFrames} is not a multiple of ${BEAT}`);
    cursor = s.from + s.durationInFrames;
  }
  if (cursor !== TOTAL_FRAMES) errors.push(`Scenes end at ${cursor}, expected ${TOTAL_FRAMES}`);
  vo.forEach((l, i) => {
    const s = scenes.find((x) => x.id === l.scene);
    if (!s || l.from < s.from || l.from >= s.from + s.durationInFrames) errors.push(`VO line ${l.n} (${l.from}) is outside scene ${l.scene}`);
    if (l.from % BEAT !== 0) errors.push(`VO line ${l.n} start ${l.from} is not on a beat`);
    if (l.to <= l.from) errors.push(`VO line ${l.n} ends before it starts`);
    if (i > 0 && l.from < vo[i - 1].to) errors.push(`VO line ${l.n} starts before line ${vo[i - 1].n} ends`);
  });
  return errors;
};

/** The VO line whose slot contains `frame`, if any. */
export const voAt = (frame: number): VoLine | undefined => VO.find((l) => frame >= l.from && frame < l.to);
