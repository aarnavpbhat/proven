// Scene 1 · Hook (0–240), VO 1. One month-end sentence at headline size: its amount, reason and account are
// marked as the parts a reader would check, then the ledger it must agree with rises beneath it.
// Principles: staging (one sentence fills the frame), timing (marks land with the VO), slow in / slow out,
// anticipation (each underline draws before its label), overlapping action (labels trail their rules by 4 frames),
// secondary action (slow push-in all scene). No accent colour yet: nothing has been checked.
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { COLORS, STROKE, TYPE } from '../brand/tokens';
import { Eyebrow, eyebrowStyle } from '../components/ui';
import { LUMEN, usd } from '../data/cases';
import { mix, progress, rise } from '../lib/anim';
import { TABULAR, css } from '../lib/svg';
import { HERO_LH, HERO_SIZE, HERO_TOP, HERO_X, PARTS, heroWords, segments, type PartId } from './shared/hero';

export const S1_LEN = 240;
export const T1 = {
  words: 4,
  amount: 66,
  reason: 78,
  account: 90,
  ledger: 112,
} as const;

/** Ledger card under the sentence (S2 carries it into the deterministic zone). */
export const S1_LEDGER = { x: 860, y: 742, w: 900, h: 200 } as const;
export const LEDGER_ROWS = LUMEN.c1.ledger.filter((r) => r.period === 'current');
export const LEDGER_ROW_H = 44;
export const LEDGER_HEAD = 58;

/** Scene-long push, anchored left of centre so nothing drifts toward the face-cam corner. */
export const s1Push = (frame: number): number => mix(1, 1.03, progress(frame, 0, S1_LEN, 'standard'));
export const S1_ORIGIN = { x: 960, y: 420 } as const;

export const LedgerCard: React.FC<{ frame: number; rowsAt: number; x: number; y: number; w: number; opacity?: number; scan?: number }> = ({ frame, rowsAt, x, y, w, opacity = 1, scan = 0 }) => (
  <div
    style={{
      position: 'absolute',
      left: x,
      top: y,
      width: w,
      height: LEDGER_HEAD + LEDGER_ROWS.length * LEDGER_ROW_H + 12,
      borderRadius: 16,
      backgroundColor: COLORS.paper,
      boxShadow: `0 0 0 1px ${COLORS.hairline}`,
      opacity,
    }}
  >
    {/* A reading band walks down the rows: the sentence is about to be checked against them. */}
    {scan > 0 && scan < 1 && (
      <div style={{ position: 'absolute', left: 8, right: 8, top: LEDGER_HEAD + scan * (LEDGER_ROWS.length - 1) * LEDGER_ROW_H, height: LEDGER_ROW_H, borderRadius: 8, backgroundColor: COLORS.surface, opacity: 1 - Math.max(0, (scan - 0.8) / 0.2) }} />
    )}
    <div style={{ position: 'absolute', left: 28, top: 18, display: 'flex', gap: 16, alignItems: 'baseline' }}>
      <span style={eyebrowStyle(COLORS.ash)}>Ledger · Legal · Oct 2026</span>
    </div>
    {LEDGER_ROWS.map((r, i) => (
      <div
        key={r.id}
        style={{
          position: 'absolute',
          left: 28,
          right: 28,
          top: LEDGER_HEAD + i * LEDGER_ROW_H,
          height: LEDGER_ROW_H,
          display: 'flex',
          alignItems: 'center',
          gap: 20,
          borderTop: `1px solid ${COLORS.hairline}`,
          ...rise(frame, rowsAt + i * 4, 12, 10),
        }}
      >
        <span style={{ ...css('mono', TYPE.eyebrow, COLORS.ash) }}>{r.id}</span>
        <span style={{ ...css('sans', TYPE.eyebrow, COLORS.ink), flex: 1, overflow: 'hidden' }}>{r.memo}</span>
        <span style={{ ...css('sans', TYPE.eyebrow, COLORS.ink), ...TABULAR }}>{usd(r.amount)}</span>
      </div>
    ))}
  </div>
);

const PartMark: React.FC<{ id: PartId; frame: number; at: number }> = ({ id, frame, at }) => {
  const words = heroWords();
  const segs = segments(words, PARTS[id].from, PARTS[id].to);
  const last = segs[segs.length - 1];
  const ruleY = (top: number) => top + HERO_SIZE * 1.36;
  return (
    <>
      {segs.map((s, k) => (
        <div
          key={k}
          style={{
            position: 'absolute',
            left: s.x0,
            top: ruleY(s.top),
            width: (s.x1 - s.x0) * progress(frame, at + k * 5, 12),
            height: STROKE.rule + 1,
            backgroundColor: COLORS.ink,
          }}
        />
      ))}
      <Eyebrow style={{ position: 'absolute', left: segs[0].x0, top: ruleY(last.top) + 9, ...(segs.length > 1 ? { left: last.x0 } : {}), ...rise(frame, at + 4 + (segs.length - 1) * 5, 10, 8) }}>
        {PARTS[id].label}
      </Eyebrow>
    </>
  );
};

/** S1 at any frame (S2 does not reuse it; it rebuilds the carried pieces from the shared geometry). */
export const S1Frame: React.FC<{ frame: number }> = ({ frame }) => {
  const words = heroWords();
  return (
    <div style={{ position: 'absolute', inset: 0, transform: `scale(${s1Push(frame)})`, transformOrigin: `${S1_ORIGIN.x}px ${S1_ORIGIN.y}px` }}>
      <Eyebrow style={{ position: 'absolute', left: HERO_X, top: HERO_TOP - 70, ...rise(frame, 0, 12, 10) }}>{`${LUMEN.entity} · October 2026 close · operating expense commentary`}</Eyebrow>
      {words.map((w, i) => (
        <div
          key={i}
          style={{ position: 'absolute', left: w.x, top: w.y, ...css('sans', HERO_SIZE, COLORS.ink), lineHeight: HERO_LH, ...rise(frame, T1.words + i * 3, 14, 30) }}
        >
          {w.text}
        </div>
      ))}
      <PartMark id="amount" frame={frame} at={T1.amount} />
      <PartMark id="reason" frame={frame} at={T1.reason} />
      <PartMark id="account" frame={frame} at={T1.account} />
      <div style={{ position: 'absolute', inset: 0, ...rise(frame, T1.ledger, 14, 24) }}>
        <LedgerCard frame={frame} rowsAt={T1.ledger + 6} x={S1_LEDGER.x} y={S1_LEDGER.y} w={S1_LEDGER.w} scan={progress(frame, 140, 60, 'standard')} />
      </div>
    </div>
  );
};

export const S1Hook: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bone }}>
      <S1Frame frame={frame} />
    </AbsoluteFill>
  );
};

export { HERO_LH };
