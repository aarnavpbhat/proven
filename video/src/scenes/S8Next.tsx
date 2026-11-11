// Scene 8 · Path forward (3255–3420), VO 14. Bone. One step, stated without a performance claim: a local
// open-weight proposer, so no sentence leaves the building. The dashed proposer card appears inside the boundary
// that already holds the checker and the ledger, last. Carried out: the text lifts away and the close's band draws.
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { COLORS, RADII, TYPE } from '../brand/tokens';
import { Eyebrow } from '../components/ui';
import { lift, mix, progress, rise } from '../lib/anim';
import { css } from '../lib/svg';

const LEN = 165;
const OUT = 141;
const BOX = { x: 160, y: 470, w: 1600, h: 250 } as const;

const Card: React.FC<{ x: number; y: number; title: string; sub: string; dashed?: boolean; style?: React.CSSProperties }> = ({ x, y, title, sub, dashed, style }) => (
  <div
    style={{
      position: 'absolute',
      left: x,
      top: y,
      width: 400,
      height: 130,
      boxSizing: 'border-box',
      borderRadius: RADII.card,
      backgroundColor: dashed ? COLORS.bone : COLORS.paper,
      border: dashed ? `2px dashed ${COLORS.ash}` : undefined,
      boxShadow: dashed ? undefined : `0 0 0 1px ${COLORS.hairline}`,
      padding: '22px 26px',
      ...style,
    }}
  >
    <div style={css('sans', TYPE.label, COLORS.ink)}>{title}</div>
    <div style={{ ...css('sans', TYPE.eyebrow, COLORS.ash), marginTop: 10 }}>{sub}</div>
  </div>
);

export const S8Next: React.FC = () => {
  const f = useCurrentFrame();
  const out = lift(f, OUT, 12, 16);
  const draw = progress(f, 20, 24);
  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bone }}>
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${mix(1, 1.02, progress(f, 0, LEN))})`, transformOrigin: '960px 400px' }}>
        <div style={{ position: 'absolute', inset: 0, ...out }}>
        <Eyebrow style={{ position: 'absolute', left: 160, top: 150, ...rise(f, 4, 12, 8) }}>Next</Eyebrow>
        <div style={{ position: 'absolute', left: 160, top: 200, width: 1600, ...css('sans', TYPE.lead, COLORS.ink), whiteSpace: 'normal', lineHeight: 1.2, ...rise(f, 10, 14, 16) }}>
          A local open-weight proposer, so no sentence leaves the building.
        </div>
        <svg width={1920} height={1080} style={{ position: 'absolute', left: 0, top: 0 }}>
          <rect x={BOX.x} y={BOX.y} width={BOX.w} height={BOX.h} rx={RADII.card} fill="none" stroke={COLORS.ink} strokeWidth={2} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - draw} />
        </svg>
        <Eyebrow style={{ position: 'absolute', left: BOX.x + 28, top: BOX.y - 44, ...rise(f, 30, 10, 8) }}>Your machine</Eyebrow>
        <Card x={BOX.x + 1160} y={BOX.y + 60} title="Ledger" sub="the transactions" style={rise(f, 34, 12, 10)} />
        <Card x={BOX.x + 620} y={BOX.y + 60} title="Checker" sub="decides from the ledger" style={rise(f, 40, 12, 10)} />
        <Card
          x={BOX.x + 60}
          y={BOX.y + 60}
          title="Proposer"
          sub="open-weight, local"
          dashed
          style={rise(f, 60, 14, 10)}
        />
        </div>
      </div>
    </AbsoluteFill>
  );
};
