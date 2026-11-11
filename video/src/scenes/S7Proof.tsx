// Scene 7 · Proof (2655–3255), VO 12–13. Obsidian, carried from the loop's dark ground. Left, all scene: the two
// kill criteria, stated as what was stopped (100% of wrong explanations blocked, 100% of correct ones never rejected). Right, first (VO 12): eleven unseen companies in industries never used in
// development, Claude Sonnet 5.5 proposing, held-out phrasing: 81.7% of claims decided after teaching, 0 / 0.
// Right, then (VO 13): the third suite, registered in advance (checker frozen, test committed before the 13
// companies were written) and scored once: 0 of 429 wrong explanations approved, 0 of 1,193 correct ones rejected,
// 78.5% decided by the rules after teaching, wrong-approval rate under 0.7% at 95% confidence (counting claims).
// Every number from src/data/results.ts. Carried out: the ground returns to bone for the path forward.
import { AbsoluteFill, interpolateColors, useCurrentFrame } from 'remotion';
import { COLORS, STROKE, TYPE } from '../brand/tokens';
import { Eyebrow } from '../components/ui';
import { RESULTS, known } from '../data/results';
import { lift, mix, progress, rise } from '../lib/anim';
import { TABULAR, css } from '../lib/svg';

const LEN = 600;
const T = { zeros: 10, labels: 22, right: 150, big: 166, sub: 190, swap: 330, pre: 344, out: 575 } as const;
const R = RESULTS;
const P = R.preregistered;
const X = 1010;

// `at` is when the block enters; `leave` (if given) is when it lifts away. It plays on the right for VO 12, then
// settles on the left beside the pre-registered result, in place of the generic zeros it would otherwise repeat.
const Unseen: React.FC<{ f: number; x: number; at: number; leave?: number }> = ({ f, x: X, at, leave }) => {
  const t = { right: at, big: at + 16, sub: at + 40 };
  return (
  <div style={{ position: 'absolute', inset: 0, ...(leave === undefined ? {} : lift(f, leave, 12, 16)) }}>
    <Eyebrow color={COLORS.mist} style={{ position: 'absolute', left: X, top: 150, width: 720, whiteSpace: 'normal', lineHeight: 1.4, ...rise(f, t.right, 12, 8) }}>
      {`${known(R.worlds.unseen)} unseen companies · industries never used in development`}
    </Eyebrow>
    <div style={{ position: 'absolute', left: X - 10, top: 270, ...css('sans', TYPE.wordmark, COLORS.paper), ...TABULAR, lineHeight: 1, ...rise(f, t.big, 16, 24) }}>
      {known(R.worlds.sonnetDecided)}
    </div>
    <div style={{ position: 'absolute', left: X, top: 500, ...css('sans', TYPE.ui, COLORS.paper), ...rise(f, t.sub, 12, 10) }}>of claims decided after teaching</div>
    <div style={{ position: 'absolute', left: X, top: 548, ...css('sans', TYPE.ui, COLORS.mist), lineHeight: 1.3, ...rise(f, t.sub + 8, 12, 10) }}>
      {'Claude Sonnet 5.5 proposing\nheld-out phrasing'}
    </div>
    <div style={{ position: 'absolute', left: X, top: 636, ...css('sans', TYPE.ui, COLORS.paper), lineHeight: 1.3, ...rise(f, t.sub + 24, 12, 10) }}>
      {'Every wrong explanation blocked\nNo correct one rejected'}
    </div>
  </div>
);
};

const Preregistered: React.FC<{ f: number }> = ({ f }) => {
  if (f < T.pre - 2) return null;
  const rows = [
    { y: 262, v: known(P.blockedPct), label: `of ${known(P.wrongExplanations)} wrong explanations blocked` },
    { y: 474, v: known(P.keptPct), label: `of ${known(P.rightExplanations)} correct ones never rejected` },
  ];
  return (
    <div style={{ position: 'absolute', inset: 0 }}>
      <Eyebrow color={COLORS.mist} style={{ position: 'absolute', left: X, top: 150, width: 820, whiteSpace: 'normal', lineHeight: 1.4, ...rise(f, T.pre, 12, 8) }}>
        {`Pre-registered test · ${known(P.worlds)} new companies · scored once`}
      </Eyebrow>
      {rows.map((r, i) => (
        <div key={r.label}>
          <div style={{ position: 'absolute', left: X - 10, top: r.y, ...css('sans', TYPE.display, COLORS.paper), ...TABULAR, lineHeight: 1, ...rise(f, T.pre + 10 + i * 10, 14, 24) }}>{r.v}</div>
          <div style={{ position: 'absolute', left: X + 404, top: r.y + 30, width: 430, ...css('sans', TYPE.ui, COLORS.paper), whiteSpace: 'normal', lineHeight: 1.25, ...rise(f, T.pre + 18 + i * 10, 12, 10) }}>{r.label}</div>
        </div>
      ))}
      <div style={{ position: 'absolute', left: X, top: 704, width: 820, ...css('sans', TYPE.ui, COLORS.paper), whiteSpace: 'normal', lineHeight: 1.3, ...rise(f, T.pre + 44, 12, 10) }}>
        {`${known(P.sonnetDecided)} decided by the rules after teaching, Sonnet proposing`}
      </div>
      <div style={{ position: 'absolute', left: X, top: 800, width: 820, ...css('sans', TYPE.eyebrow, COLORS.mist), whiteSpace: 'normal', lineHeight: 1.35, ...rise(f, T.pre + 60, 12, 10) }}>
        {`Checker frozen and test committed before the companies were written. At 95% confidence, at least ${known(P.blockedBound95)} of wrong explanations are blocked, counting claims.`}
      </div>
    </div>
  );
};

export const S7Proof: React.FC = () => {
  const f = useCurrentFrame();
  const push = mix(1, 1.025, progress(f, 0, LEN, 'standard'));
  const out = lift(f, T.out, 12, 16);
  const bg = interpolateColors(progress(f, T.out + 6, 14), [0, 1], [COLORS.obsidian, COLORS.bone]);
  const rows = [
    { y: 250, v: known(R.bench.blockedPct), label: 'of wrong explanations blocked' },
    { y: 500, v: known(R.bench.keptPct), label: 'of correct explanations never rejected' },
  ];
  return (
    <AbsoluteFill style={{ backgroundColor: bg }}>
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${push})`, transformOrigin: '960px 480px' }}>
        <div style={{ position: 'absolute', inset: 0, ...out }}>
          <div style={{ position: 'absolute', inset: 0, ...lift(f, T.swap, 12, 16) }}>
          <Eyebrow color={COLORS.mist} style={{ position: 'absolute', left: 160, top: 150, ...rise(f, 2, 12, 8) }}>
            Safety · on every benchmark
          </Eyebrow>
          {rows.map((r, i) => (
            <div key={r.label}>
              <div style={{ position: 'absolute', left: 150, top: r.y - 40, ...css('sans', TYPE.display, COLORS.paper), ...TABULAR, lineHeight: 1, ...rise(f, T.zeros + i * 6, 14, 24) }}>{r.v}</div>
              <div style={{ position: 'absolute', left: 570, top: r.y - 10, width: 340, ...css('sans', TYPE.ui, COLORS.mist), whiteSpace: 'normal', lineHeight: 1.25, ...rise(f, T.labels + i * 6, 12, 10) }}>{r.label}</div>
            </div>
          ))}
          </div>
          <div style={{ position: 'absolute', left: 930, top: 150, width: STROKE.border, height: 720 * progress(f, T.right - 20, 24), backgroundColor: COLORS.graphite }} />
          <Unseen f={f} x={X} at={T.right} leave={T.swap} />
          {f >= T.pre - 2 ? <Unseen f={f} x={160} at={T.pre} /> : null}
          <Preregistered f={f} />
        </div>
      </div>
    </AbsoluteFill>
  );
};
