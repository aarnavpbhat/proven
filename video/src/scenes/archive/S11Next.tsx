// Scene 11 · Path forward (4260–4530), VO 15. The rule carried from S9 is a road; four next steps rise from it, each
// with its status as the docs state it (README "What this does not show", docs/finetune.md sections 6, 9, 11 and 13,
// docs/teaching.md section 3). The road then shrinks into the highlighter band under S12's wordmark.
// Principles: staging (one card per spoken item), anticipation (each card's dot lands on the road before the card
// rises), overlapping action (icon draws while the card rises), slow in / slow out, arcs (the road's end swings into
// the band), secondary action (slow push).
import { AbsoluteFill, interpolateColors, useCurrentFrame } from 'remotion';
import { COLORS, RADII, STROKE, TYPE } from '../brand/tokens';
import { Icon, type IconName } from '../components/Icons';
import { Eyebrow } from '../components/ui';
import { RESULTS, known } from '../data/results';
import { lift, mix, progress, rise } from '../lib/anim';
import { css } from '../lib/svg';
import { ROAD } from './shared/s9-geom';
import { BAND_START, band } from './shared/s11-geom';

const LEN = 270;
const OUT = 236;
const CARD = { y: 344, w: 380, h: 360, gap: 26 } as const;

const ITEMS: { at: number; icon: IconName; title: string; body: string }[] = [
  { at: 18, icon: 'layers', title: 'Larger students', body: `A stable 7B fine-tune (the first diverged). RL is built; ${known(RESULTS.rl.steps)} steps did not yet show it helps.` },
  { at: 74, icon: 'gate', title: 'Test the rules anew', body: 'The lesson rules were fit to these suites, and the gate cannot test words it has never seen.' },
  { at: 132, icon: 'ledger', title: "Real companies' ledgers", body: "No real company's commentary has been checked yet. CSV import already works." },
  {
    at: 176,
    icon: 'person',
    title: 'Less reviewer time',
    body: `When phrases repeat, ask about the commonest first: 5 confirmations decide ${known(RESULTS.order.frequencyAt5)}, not ${known(RESULTS.order.arrivalAt5)}.`,
  },
];

export const S11Next: React.FC = () => {
  const f = useCurrentFrame();
  const push = mix(1, 1.02, progress(f, 0, LEN, 'standard'));
  const out = lift(f, OUT, 10, 16);
  const roadT = progress(f, OUT, LEN - 1 - OUT, 'standard');
  const b = band();
  const road = {
    x: mix(960 + (ROAD.x - 960) * push, b.x, roadT),
    y: mix(900 + (ROAD.y - 900) * push, b.y, roadT) + Math.sin(Math.PI * roadT) * 60,
    w: mix(ROAD.w * push, b.w * BAND_START, roadT),
    h: mix(STROKE.rule, b.h, roadT),
  };

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bone }}>
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${push})`, transformOrigin: '960px 900px' }}>
        <div style={{ position: 'absolute', inset: 0, ...out }}>
          <Eyebrow style={{ position: 'absolute', left: 160, top: 156, ...rise(f, 4, 10, 8) }}>Path forward</Eyebrow>
          <div style={{ position: 'absolute', left: 160, top: 196, ...css('sans', TYPE.title, COLORS.ink), lineHeight: 1.1, ...rise(f, 8, 12, 12) }}>What comes next</div>
          {/* Secondary action: a marker walks the road from the first step to the last while the cards settle. */}
          {(() => {
            const t = progress(f, 40, OUT - 40, 'standard');
            const x = mix(ROAD.x + 30, ROAD.x + 3 * (CARD.w + CARD.gap) + 30, t);
            return <div style={{ position: 'absolute', left: x - 14, top: ROAD.y - 14 + 1, width: 28, height: 28, borderRadius: 14, boxSizing: 'border-box', border: `3px solid ${COLORS.ink}`, backgroundColor: COLORS.bone, opacity: progress(f, 36, 8) }} />;
          })()}
          {ITEMS.map((it, i) => {
            const x = ROAD.x + i * (CARD.w + CARD.gap);
            const dot = progress(f, it.at - 4, 8);
            return (
              <div key={it.title}>
                <div style={{ position: 'absolute', left: x + 30 - 9, top: ROAD.y - 9 + 1, width: 18, height: 18, borderRadius: 9, backgroundColor: COLORS.ink, transform: `scale(${dot})` }} />
                <div
                  style={{
                    position: 'absolute',
                    left: x,
                    top: CARD.y,
                    width: CARD.w,
                    height: CARD.h,
                    boxSizing: 'border-box',
                    padding: '28px 28px',
                    borderRadius: RADII.card,
                    backgroundColor: COLORS.paper,
                    boxShadow: `0 0 0 1px ${COLORS.hairline}`,
                    ...rise(f, it.at, 14, 18),
                  }}
                >
                  <Icon name={it.icon} size={40} color={COLORS.ink} t={progress(f, it.at + 4, 14)} />
                  <div style={{ ...css('sans', TYPE.ui, COLORS.ink), marginTop: 22, whiteSpace: 'normal', lineHeight: 1.15 }}>{it.title}</div>
                  <div style={{ ...css('sans', 30, COLORS.ash), whiteSpace: 'normal', lineHeight: 1.3, marginTop: 16 }}>{it.body}</div>
                </div>
              </div>
            );
          })}
        </div>
      </div>
      {/* The road: carried from S9, it becomes the band under the wordmark. */}
      <div
        style={{
          position: 'absolute',
          left: road.x,
          top: road.y,
          width: road.w,
          height: road.h,
          backgroundColor: interpolateColors(roadT, [0, 0.5, 1], [COLORS.ink, COLORS.chartreuse, COLORS.chartreuse]),
          borderRadius: road.h / 2 > 6 ? 6 : road.h / 2,
        }}
      />
    </AbsoluteFill>
  );
};
