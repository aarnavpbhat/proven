// Scene 6 · Architecture loop (2325–2655), VO 11. Adapted from the archived S4Loop: the whole system as one diagram
// that builds along the path a claim takes: explanation and chart → proposer (a language model; untrusted, dashed;
// no verdict field) → admission → checker, fed by the ledger → PASS / FAIL / REVIEW; REVIEW → reviewer → safety
// gate → lessons → back into the checker, so the rules decide the next close. The lesson from the walkthrough
// ("our biggest promotion of the year" → campaign) sits in the lessons node. The original timings play 1.1x slower. Carried out: the ground turns obsidian for the proof.
import { AbsoluteFill, interpolateColors, useCurrentFrame } from 'remotion';
import { COLORS, RADII, STROKE, TYPE } from '../brand/tokens';
import { Icon, type IconName } from '../components/Icons';
import { Eyebrow, VerdictChip } from '../components/ui';
import { drawOn, enter, lift, mix, progress, rise } from '../lib/anim';
import { css } from '../lib/svg';
import { BRIGHTFIELD } from '../data/cases';
import { BOUNDARY_X, LESSON_PILL, NODES, VERDICT_CHIPS, verdictChipPos, type NodeId } from './shared/loop-geom';

const LEN = 300;
/** The archived 300-frame choreography, played 1.1x slower to fill 330 frames; the ground is dark by the last frame. */
const SLOW = 1.1;
const AT: Record<NodeId, number> = {
  lessons: 0,
  explanation: 10,
  chart: 14,
  proposer: 34,
  admission: 66,
  ledger: 82,
  checker: 92,
  verdicts: 112,
  reviewer: 150,
  gate: 172,
};
const OUT = 262;

const LABELS: Record<NodeId, { title: string; sub?: string; icon?: IconName; dashed?: boolean }> = {
  explanation: { title: 'Explanation', sub: 'the commentary', icon: 'doc' },
  chart: { title: 'Chart of accounts', sub: 'names only', icon: 'ledger' },
  proposer: { title: 'Proposer', icon: 'chip', dashed: true },
  admission: { title: 'Admission', sub: 'copied, on chart', icon: 'gate' },
  ledger: { title: 'Ledger', sub: 'the transactions', icon: 'ledger' },
  checker: { title: 'Checker', sub: 'stdlib Python', icon: 'shield' },
  verdicts: { title: '' },
  reviewer: { title: 'Reviewer', sub: 'confirms once', icon: 'person' },
  gate: { title: 'Safety gate', sub: 'known answers', icon: 'check' },
  lessons: { title: 'Lessons', icon: 'book' },
};

const c = (id: NodeId) => NODES[id];
const mid = (id: NodeId) => ({ x: c(id).x + c(id).w / 2, y: c(id).y + c(id).h / 2 });

// Edges as SVG paths, in draw order, with the frame each starts drawing.
const EDGES: { d: string; at: number; dur: number }[] = [
  { d: `M ${c('explanation').x + c('explanation').w} ${mid('explanation').y} H 520 V ${mid('proposer').y - 30} H ${c('proposer').x}`, at: 22, dur: 14 },
  { d: `M ${c('chart').x + c('chart').w} ${mid('chart').y} H 520 V ${mid('proposer').y + 30} H ${c('proposer').x}`, at: 24, dur: 14 },
  { d: `M ${c('proposer').x + c('proposer').w} ${mid('admission').y} H ${c('admission').x}`, at: 54, dur: 14 },
  { d: `M ${c('admission').x + c('admission').w} ${mid('checker').y} H ${c('checker').x}`, at: 80, dur: 10 },
  { d: `M ${mid('ledger').x} ${c('ledger').y + c('ledger').h} V ${c('checker').y}`, at: 88, dur: 8 },
  { d: `M ${c('checker').x + c('checker').w} ${mid('checker').y} H ${c('verdicts').x}`, at: 104, dur: 8 },
  { d: `M ${mid('verdicts').x} ${c('verdicts').y + c('verdicts').h} V ${c('reviewer').y}`, at: 120, dur: 16 },
  { d: `M ${c('reviewer').x} ${mid('reviewer').y} H ${c('gate').x + c('gate').w}`, at: 162, dur: 10 },
  { d: `M ${c('gate').x} ${mid('gate').y} H ${c('lessons').x + c('lessons').w}`, at: 184, dur: 10 },
  // The return: lessons → up and over → into the checker from below.
  { d: `M ${mid('lessons').x} ${c('lessons').y} V 540 Q ${mid('lessons').x} 520 ${mid('lessons').x + 20} 520 H ${mid('checker').x - 20} Q ${mid('checker').x} 520 ${mid('checker').x} 500 V ${c('checker').y + c('checker').h}`, at: 200, dur: 30 },
];

const Arrowhead: React.FC<{ x: number; y: number; dir: 'right' | 'left' | 'up' | 'down'; t: number; color: string }> = ({ x, y, dir, t, color }) => {
  if (t < 1) return null;
  const rot = { right: 0, down: 90, left: 180, up: 270 }[dir];
  return <path d="M -10 -7 L 0 0 L -10 7" transform={`translate(${x} ${y}) rotate(${rot})`} fill="none" stroke={color} strokeWidth={STROKE.edge} strokeLinecap="round" strokeLinejoin="round" />;
};

const HEADS: { x: number; y: number; dir: 'right' | 'left' | 'up' | 'down' }[] = [
  { x: c('proposer').x, y: mid('proposer').y - 30, dir: 'right' },
  { x: c('proposer').x, y: mid('proposer').y + 30, dir: 'right' },
  { x: c('admission').x, y: mid('admission').y, dir: 'right' },
  { x: c('checker').x, y: mid('checker').y, dir: 'right' },
  { x: mid('ledger').x, y: c('checker').y, dir: 'down' },
  { x: c('verdicts').x, y: mid('checker').y, dir: 'right' },
  { x: mid('verdicts').x, y: c('reviewer').y, dir: 'down' },
  { x: c('gate').x + c('gate').w, y: mid('reviewer').y, dir: 'left' },
  { x: c('lessons').x + c('lessons').w, y: mid('gate').y, dir: 'left' },
  { x: mid('checker').x, y: c('checker').y + c('checker').h, dir: 'up' },
];

const Node: React.FC<{ id: NodeId; f: number; at: number; children?: React.ReactNode }> = ({ id, f, at, children }) => {
  const b = c(id);
  const L = LABELS[id];
  const t = progress(f, at, 14);
  return (
    <div
      style={{
        position: 'absolute',
        left: b.x,
        top: b.y,
        width: b.w,
        height: b.h,
        boxSizing: 'border-box',
        borderRadius: RADII.card,
        backgroundColor: L.dashed ? 'transparent' : COLORS.paper,
        border: L.dashed ? `2px dashed ${COLORS.ash}` : undefined,
        boxShadow: L.dashed ? undefined : `0 0 0 1px ${COLORS.hairline}`,
        opacity: t,
        transform: `translateY(${(1 - enter(f, at, 14)) * 14}px)`,
      }}
    >
      {L.title && (
        <div style={{ position: 'absolute', left: 22, top: 18, display: 'flex', alignItems: 'center', gap: 12 }}>
          {L.icon && <Icon name={L.icon} size={30} color={COLORS.ink} t={progress(f, at + 4, 12)} />}
          <span style={css('sans', TYPE.label, COLORS.ink)}>{L.title}</span>
        </div>
      )}
      {L.sub && <div style={{ position: 'absolute', left: 22, top: 62, ...css('sans', TYPE.eyebrow, COLORS.ash) }}>{L.sub}</div>}
      {children}
    </div>
  );
};

const LessonText: React.FC = () => (
  <div style={{ ...css('sans', TYPE.eyebrow, COLORS.ink), whiteSpace: 'normal', lineHeight: 1.3 }}>
    {`“${BRIGHTFIELD.lesson.trigger}”`}
    <br />
    {`→ ${BRIGHTFIELD.lesson.terms[0]}`}
  </div>
);

export const S6Loop: React.FC = () => {
  const f = useCurrentFrame() / SLOW;
  const push = mix(1, 1.03, progress(f, 0, LEN, 'standard'));
  const out = lift(f, OUT, 12, 16);
  const toDark = progress(f, OUT + 14, 10);
  const bg = interpolateColors(toDark, [0, 1], [COLORS.bone, COLORS.obsidian]);
  // A token travels the path once with the VO.
  // The token travels along the edges only; it is hidden while it crosses a node, so it never covers a label.
  const n = (id: NodeId) => c(id);
  const tokenPath: { x: number; y: number; at: number; show: boolean }[] = [
    { x: n('explanation').x + n('explanation').w, y: mid('explanation').y, at: 22, show: true },
    { x: n('proposer').x, y: mid('proposer').y - 30, at: 36, show: true },
    { x: n('proposer').x + n('proposer').w, y: mid('admission').y, at: 50, show: false },
    { x: n('admission').x, y: mid('admission').y, at: 62, show: true },
    { x: n('admission').x + n('admission').w, y: mid('checker').y, at: 78, show: false },
    { x: n('checker').x, y: mid('checker').y, at: 88, show: true },
    { x: n('checker').x + n('checker').w, y: mid('checker').y, at: 100, show: false },
    { x: n('verdicts').x, y: mid('checker').y, at: 108, show: true },
    { x: mid('verdicts').x, y: n('verdicts').y + n('verdicts').h, at: 118, show: false },
    { x: mid('verdicts').x, y: n('reviewer').y, at: 136, show: true },
    { x: n('reviewer').x, y: mid('reviewer').y, at: 152, show: false },
    { x: n('gate').x + n('gate').w, y: mid('gate').y, at: 160, show: true },
    { x: n('gate').x, y: mid('gate').y, at: 176, show: false },
    { x: n('lessons').x + n('lessons').w, y: mid('lessons').y, at: 184, show: true },
    { x: mid('lessons').x, y: n('lessons').y, at: 200, show: false },
    { x: mid('lessons').x, y: 520, at: 206, show: true },
    { x: mid('checker').x, y: 520, at: 222, show: true },
    { x: mid('checker').x, y: n('checker').y + n('checker').h, at: 232, show: true },
  ];
  let token: { x: number; y: number } | null = null;
  for (let i = 1; i < tokenPath.length; i++) {
    const a = tokenPath[i - 1];
    const b = tokenPath[i];
    if (f >= a.at && f < b.at && b.show) {
      const t = progress(f, a.at, b.at - a.at, 'standard');
      token = { x: mix(a.x, b.x, t), y: mix(a.y, b.y, t) };
    }
  }

  return (
    <AbsoluteFill style={{ backgroundColor: bg }}>
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${push})`, transformOrigin: '960px 450px' }}>
        <div style={{ position: 'absolute', inset: 0, ...out }}>
          {/* Trust boundary */}
          <div style={{ position: 'absolute', left: BOUNDARY_X, top: 150, width: STROKE.rule, height: 350 * progress(f, 28, 20), backgroundColor: COLORS.ink }} />
          <Eyebrow style={{ position: 'absolute', left: BOUNDARY_X - 420, top: 470, width: 390, textAlign: 'right', ...rise(f, 30, 10, 8) }}>Untrusted · proposes</Eyebrow>
          <Eyebrow style={{ position: 'absolute', left: BOUNDARY_X + 30, top: 470, ...rise(f, 34, 10, 8) }}>Deterministic · decides</Eyebrow>
          <svg width={1920} height={1080} style={{ position: 'absolute', left: 0, top: 0 }}>
            {EDGES.map((e, i) => {
              const t = progress(f, e.at, e.dur, 'standard');
              return (
                <g key={i}>
                  <path d={e.d} fill="none" stroke={COLORS.ink} strokeWidth={STROKE.edge} strokeLinecap="round" strokeLinejoin="round" {...drawOn(t)} />
                  <Arrowhead {...HEADS[i]} t={t} color={COLORS.ink} />
                </g>
              );
            })}
          </svg>
          <Node id="explanation" f={f} at={AT.explanation} />
          <Node id="chart" f={f} at={AT.chart} />
          <Node id="proposer" f={f} at={AT.proposer}>
            {['a language model', 'proposes claims', 'no verdict field'].map((t, i) => (
              <div key={t} style={{ position: 'absolute', left: 22, top: 70 + i * 48, display: 'flex', alignItems: 'center', gap: 12, ...rise(f, AT.proposer + 8 + i * 4, 10, 8) }}>
                <span style={{ width: 10, height: 10, borderRadius: 5, backgroundColor: COLORS.ink }} />
                <span style={css('sans', TYPE.eyebrow, COLORS.ink)}>{t}</span>
              </div>
            ))}
          </Node>
          <Node id="admission" f={f} at={AT.admission} />
          <Node id="ledger" f={f} at={AT.ledger} />
          <Node id="checker" f={f} at={AT.checker} />
          <Node id="reviewer" f={f} at={AT.reviewer} />
          <Node id="gate" f={f} at={AT.gate} />
          <div style={{ position: 'absolute', left: 1000, top: 534, ...rise(f, 222, 12, 8) }}>
            <span style={css('sans', TYPE.eyebrow, COLORS.ink)}>next close: the rules decide, no model</span>
          </div>
          {/* Verdict node: frame only; its chips are drawn outside `out` so FAIL and PASS can carry into S5. */}
          <Node id="verdicts" f={f} at={AT.verdicts} />
        </div>
        {/* Lessons node holds the carried pill from frame 0 (its frame draws around it). */}
        <div style={{ position: 'absolute', inset: 0, ...out }}>
          <div
            style={{
              position: 'absolute',
              left: c('lessons').x,
              top: c('lessons').y,
              width: c('lessons').w,
              height: c('lessons').h,
              borderRadius: RADII.card,
              backgroundColor: COLORS.paper,
              boxShadow: `0 0 0 1px ${COLORS.hairline}`,
              opacity: progress(f, 0, 14),
            }}
          >
            <div style={{ position: 'absolute', left: 24, top: 18, display: 'flex', alignItems: 'center', gap: 12, ...rise(f, 4, 10, 6) }}>
              <Icon name="book" size={30} color={COLORS.ink} t={progress(f, 6, 12)} />
              <span style={css('sans', TYPE.label, COLORS.ink)}>Lessons</span>
            </div>
          </div>
          <div style={{ position: 'absolute', left: LESSON_PILL.x, top: LESSON_PILL.y, width: LESSON_PILL.w, boxSizing: 'border-box', padding: '8px 14px', borderRadius: RADII.control, backgroundColor: COLORS.chartreuse, ...rise(f, 6, 12, 10) }}>
            <LessonText />
          </div>
          {token && <div style={{ position: 'absolute', left: token.x - 9, top: token.y - 9, width: 18, height: 18, borderRadius: 9, backgroundColor: COLORS.ink, boxShadow: `0 0 0 4px ${COLORS.bone}` }} />}
        </div>
      </div>
      {/* Verdict chips, inside the verdict node; they leave with the diagram. */}
      {VERDICT_CHIPS.map((v, i) => {
        const p0 = verdictChipPos(i);
        const appear = rise(f, AT.verdicts + 6 + i * 4, 10, 8);
        const o = lift(f, OUT, 12, 16);
        return (
          <div key={v} style={{ position: 'absolute', left: 960 + (p0.x - 960) * push, top: 450 + (p0.y - 450) * push, transform: `scale(${push})`, transformOrigin: '0 0', opacity: appear.opacity * o.opacity }}>
            <VerdictChip verdict={v} size={TYPE.eyebrow} />
          </div>
        );
      })}
    </AbsoluteFill>
  );
};
