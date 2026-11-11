// Scene 5 · Kill criteria (1710–2010), VO 8. The FAIL and PASS chips carried from the diagram become the two numbers
// that must stay at zero; every benchmark lands with its pair of zeros; then the teaching curve shows what lessons buy
// with both still at zero. All numbers from src/data/results.ts.
// Principles: staging (two big zeros hold the left half all scene), anticipation (each row's zeros land after its
// label), follow-through (rows settle in a 4-frame stagger), slow in / slow out on the curve's draw, secondary action
// (slow push), timing (rows on beats).
import { AbsoluteFill, interpolateColors, useCurrentFrame } from 'remotion';
import { COLORS, STROKE, TYPE } from '../brand/tokens';
import { Eyebrow, VerdictChip } from '../components/ui';
import { RESULTS, known, num, type Stat } from '../data/results';
import { drawOn, lift, mix, progress, rise } from '../lib/anim';
import { TABULAR, css } from '../lib/svg';
import { S5_CHIPS } from './shared/s5-geom';
import { LAPTOP_BASE } from './shared/s7-geom';

const LEN = 300;
const T = { labels: 6, zeros: 14, rows: 30, rowsOut: 150, chart: 178, line: 188, lineEnd: 246, note: 252, out: 282 } as const;
const R = RESULTS;

interface BenchRow {
  label: string;
  fail: Stat | null; // null: not reported for this benchmark (shown as a dash)
  pass: Stat;
}

const ROWS: BenchRow[] = [
  { label: `${known(R.bench.closes)} closes, seen phrasing`, fail: R.bench.seenControlFail, pass: R.bench.seenUnsafePass },
  { label: `${known(R.bench.closes)} closes, held-out phrasing`, fail: R.bench.heldoutControlFail, pass: R.bench.heldoutUnsafePass },
  { label: `After teaching, ${known(R.teachMeasured)} untaught closes`, fail: R.teachControlFail, pass: R.teachUnsafePass },
  { label: `${known(R.worlds.unseen)} unseen worlds, five proposers, every step`, fail: R.worlds.qwenRebuiltControlFail, pass: R.worlds.qwenRebuiltUnsafePass },
  { label: `${known(R.sealed.worlds)} sealed worlds, under the final rules`, fail: R.sealed.sonnetControlFail, pass: R.sealed.unsafeAfter },
  { label: 'Careless reviewer, safety gate on', fail: R.gate.carelessControlFailOn, pass: R.gate.carelessUnsafeOn },
  { label: `${known(R.redteam.rewordings)} reworded wrong explanations`, fail: null, pass: R.redteam.rewordedPassedAfter },
  { label: `${known(R.redteam.lyingProposals)} proposals from a lying model`, fail: null, pass: R.redteam.lyingPassed },
];

const COL = { fail: 1556, pass: 1686 } as const;
const CHART = { x: 1060, y: 200, w: 680, h: 400 } as const;
const MAX_TAUGHT = 110;

export const S5Zero: React.FC = () => {
  const f = useCurrentFrame();
  const push = mix(1, 1.025, progress(f, 0, LEN, 'standard'));
  const out = lift(f, T.out, 10, 16);
  const rowsOut = (i: number) => lift(f, T.rowsOut + i * 2, 10, 14);
  const curve = R.teachCurve.map((p) => ({ x: CHART.x + (p.taught / MAX_TAUGHT) * CHART.w, y: CHART.y + CHART.h * (1 - (num(p.decided) ?? 0) / 100), p }));
  const d = curve.map((q, i) => `${i ? 'L' : 'M'} ${q.x} ${q.y}`).join(' ');
  const lineT = progress(f, T.line, T.lineEnd - T.line, 'standard');

  return (
    <AbsoluteFill style={{ backgroundColor: interpolateColors(progress(f, T.out + 4, 10), [0, 1], [COLORS.obsidian, COLORS.bone]) }}>
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${push})`, transformOrigin: '960px 900px' }}>
        <div style={{ position: 'absolute', inset: 0, ...out }}>
          <Eyebrow color={COLORS.mist} style={{ position: 'absolute', left: 160, top: 140, ...rise(f, 2, 12, 8) }}>
            Kill criteria · both must be zero
          </Eyebrow>
          {[
            { y: S5_CHIPS.fail.y, label: 'correct explanations failed', v: known(R.bench.heldoutControlFail) },
            { y: S5_CHIPS.pass.y, label: 'wrong explanations passed', v: known(R.bench.heldoutUnsafePass) },
          ].map((r, i) => (
            <div key={r.label}>
              <div style={{ position: 'absolute', left: 160, top: r.y + 92, ...css('sans', TYPE.ui, COLORS.mist), ...rise(f, T.labels + i * 4, 12, 10) }}>{r.label}</div>
              <div style={{ position: 'absolute', left: 660, top: r.y - 52, ...css('sans', TYPE.wordmark, COLORS.paper), ...TABULAR, lineHeight: 1, ...rise(f, T.zeros + i * 4, 14, 24) }}>{r.v}</div>
            </div>
          ))}
          <div style={{ position: 'absolute', left: 900, top: 150, width: STROKE.border, height: 560 * progress(f, 10, 20), backgroundColor: COLORS.graphite }} />

          {/* Benchmarks, each with its two zeros */}
          <div style={{ position: 'absolute', left: COL.fail, top: 140, ...rise(f, T.rows - 6, 10, 8), ...rowsOut(0) }}>
            <VerdictChip verdict="FAIL" size={TYPE.eyebrow} />
          </div>
          <div style={{ position: 'absolute', left: COL.pass, top: 140, ...rise(f, T.rows - 4, 10, 8), ...rowsOut(0) }}>
            <VerdictChip verdict="PASS" size={TYPE.eyebrow} />
          </div>
          {ROWS.map((r, i) => {
            const y = 214 + i * 64;
            const at = T.rows + i * 9;
            const o = rowsOut(i + 1);
            const zero = (st: Stat | null) => (st === null ? '—' : known(st));
            return (
              <div key={r.label} style={{ position: 'absolute', left: 960, top: y, width: 800, height: 56, borderTop: `1px solid ${COLORS.graphite}`, ...o }}>
                <div style={{ position: 'absolute', left: 0, top: 12, ...css('sans', TYPE.eyebrow, COLORS.paper), ...rise(f, at, 10, 8) }}>{r.label}</div>
                <div style={{ position: 'absolute', left: COL.fail - 960 + 30, top: 8, ...css('sans', TYPE.label, r.fail ? COLORS.paper : COLORS.mist), ...TABULAR, ...rise(f, at + 5, 8, 6) }}>{zero(r.fail)}</div>
                <div style={{ position: 'absolute', left: COL.pass - 960 + 30, top: 8, ...css('sans', TYPE.label, COLORS.paper), ...TABULAR, ...rise(f, at + 7, 8, 6) }}>{zero(r.pass)}</div>
              </div>
            );
          })}

          {/* The teaching curve: decided without a person, untaught closes, rules only */}
          {f >= T.chart && (
            <>
              <Eyebrow color={COLORS.mist} style={{ position: 'absolute', left: 960, top: 140, ...rise(f, T.chart, 10, 8) }}>
                Decided without a person, after teaching
              </Eyebrow>
              <svg width={1920} height={1080} style={{ position: 'absolute', left: 0, top: 0 }}>
                <line x1={CHART.x} y1={CHART.y + CHART.h} x2={CHART.x + CHART.w * progress(f, T.chart, 16)} y2={CHART.y + CHART.h} stroke={COLORS.graphite} strokeWidth={2} />
                {[50, 100].map((g) => (
                  <line key={g} x1={CHART.x} x2={CHART.x + CHART.w * progress(f, T.chart + 4, 16)} y1={CHART.y + CHART.h * (1 - g / 100)} y2={CHART.y + CHART.h * (1 - g / 100)} stroke={COLORS.graphite} strokeWidth={1} strokeDasharray="4 8" />
                ))}
                {f < T.out && <path d={d} fill="none" stroke={COLORS.paper} strokeWidth={4} strokeLinecap="round" strokeLinejoin="round" {...drawOn(lineT)} />}
                {curve.map((q, i) => {
                  const at = T.line + (q.p.taught / MAX_TAUGHT) * (T.lineEnd - T.line);
                  const t = progress(f, at, 6);
                  return <circle key={i} cx={q.x} cy={q.y} r={8 * t} fill={COLORS.paper} />;
                })}
              </svg>
              {[50, 100].map((g) => (
                <div key={g} style={{ position: 'absolute', left: 960, top: CHART.y + CHART.h * (1 - g / 100) - 18, ...css('sans', TYPE.eyebrow, COLORS.mist), ...TABULAR, ...rise(f, T.chart + 6, 10, 6) }}>{`${g}%`}</div>
              ))}
              {curve.map((q, i) => {
                const at = T.line + (q.p.taught / MAX_TAUGHT) * (T.lineEnd - T.line);
                return (
                  <div key={i}>
                    <div style={{ position: 'absolute', left: q.x - 40, top: q.y - (i < 2 ? 16 : 56), width: 80, textAlign: 'center', ...css('sans', TYPE.eyebrow, COLORS.paper), ...TABULAR, ...rise(f, at + 2, 8, 6), ...(i < 2 ? { left: q.x + 18, textAlign: 'left' } : {}) }}>
                      {known(q.p.decided)}
                    </div>
                    <div style={{ position: 'absolute', left: q.x - 40, top: CHART.y + CHART.h + 14, width: 80, textAlign: 'center', ...css('sans', TYPE.eyebrow, COLORS.mist), ...TABULAR, ...rise(f, T.chart + 8 + i * 2, 8, 6) }}>{q.p.taught}</div>
                  </div>
                );
              })}
              <div style={{ position: 'absolute', left: CHART.x, top: CHART.y + CHART.h + 60, ...css('sans', TYPE.eyebrow, COLORS.mist), ...rise(f, T.chart + 14, 10, 6) }}>closes taught from</div>
              <div style={{ position: 'absolute', left: 960, top: CHART.y + CHART.h + 108, ...css('sans', TYPE.eyebrow, COLORS.paper), ...rise(f, T.note, 10, 8) }}>
                {`${known(R.teachControlFail)} correct failed · ${known(R.teachUnsafePass)} wrong passed, at every point`}
              </div>
            </>
          )}
        </div>
      </div>
      {/* The carried chips (from S4's verdict node) stay in place and leave with the scene. */}
      {(['fail', 'pass'] as const).map((k) => {
        const a = S5_CHIPS[k];
        const s = (a.size / TYPE.eyebrow) * push;
        return (
          <div key={k} style={{ position: 'absolute', left: 960 + (a.x - 960) * push, top: 900 + (a.y - 900) * push, transform: `${out.transform} scale(${s})`, transformOrigin: '0 0', opacity: out.opacity }}>
            <VerdictChip verdict={k === 'fail' ? 'FAIL' : 'PASS'} size={TYPE.eyebrow} />
          </div>
        );
      })}
      {/* Carried out: the teaching curve flattens into the laptop's base line (S6). */}
      {f >= T.out &&
        (() => {
          const t = progress(f, T.out, LEN - 1 - T.out, 'standard');
          const pts = curve.map((q, i) => {
            const sx = 960 + (q.x - 960) * push;
            const sy = 900 + (q.y - 900) * push;
            const tx = LAPTOP_BASE.x0 + ((LAPTOP_BASE.x1 - LAPTOP_BASE.x0) * i) / (curve.length - 1);
            return `${i ? 'L' : 'M'} ${mix(sx, tx, t)} ${mix(sy, LAPTOP_BASE.y, t)}`;
          });
          return (
            <svg width={1920} height={1080} style={{ position: 'absolute', left: 0, top: 0 }}>
              <path d={pts.join(' ')} fill="none" stroke={interpolateColors(t, [0, 1], [COLORS.paper, COLORS.ink])} strokeWidth={mix(4, 3, t)} strokeLinecap="round" strokeLinejoin="round" />
            </svg>
          );
        })()}
    </AbsoluteFill>
  );
};
