// Scene 7 · Constrained decoding (2280–2670), VO 10. Opens inside the laptop screen from S6. A proposer's reply is
// written token by token under the mask of training/constrain.py: `account` may only be a chart name, figures and
// the reason may only continue a real span of the explanation (the automaton's state is the set of places the copy
// could end, drawn on the explanation as it narrows: 21 → 8 → 4 → 3 → 1), and search terms stay free text.
// The reply and the explanation are the real Brightfield Health close; the candidate tokens are illustrative.
// Principles: staging (input on top, output below, the mask on the right), anticipation (candidates appear before
// the mask strikes), follow-through (the chosen token types after the strike), timing (each typed character is a
// 12-frame step), slow in / slow out, secondary action (slow push).
import { AbsoluteFill, interpolateColors, useCurrentFrame } from 'remotion';
import { COLORS, RADII, STROKE, TYPE } from '../brand/tokens';
import { Icon } from '../components/Icons';
import { StatText, eyebrowStyle } from '../components/ui';
import { BRIGHTFIELD } from '../data/cases';
import { RESULTS, known } from '../data/results';
import { lift, mix, progress, rise } from '../lib/anim';
import { css, measure } from '../lib/svg';
import { TERMS_LINE } from './shared/s8-geom';

const LEN = 390;
const D = RESULTS.decoding;
const EXPL = { x: 160, y: 150, w: 1600, top: 204, line: 44, size: 30 } as const;
const REPLY = { x: 160, y: 426, w: 1000, top: 478, line: 44 } as const;
const PANEL = { x: 1200, y: 426, w: 560, h: 330 } as const;
const MONO = TYPE.eyebrow;
const CH = 0.6 * MONO; // IBM Plex Mono advance

const LINES = BRIGHTFIELD.explanation;

interface Step {
  key: string; // the line's fixed prefix
  value: string; // what gets typed
  at: number; // when candidates appear
  type: number; // when typing starts
  rate: number; // frames per character
  candidates: { tok: string; ok: boolean }[];
  reason: string;
}

const STEPS: Step[] = [
  {
    key: '  "account": "',
    value: 'Cloud Hosting",',
    at: 52,
    type: 90,
    rate: 1,
    candidates: [
      { tok: 'Cloud Hosting', ok: true },
      { tok: 'Hosting & CDN', ok: false },
      { tok: 'Infrastructure', ok: false },
      { tok: 'Servers', ok: false },
    ],
    reason: 'account: only a name on the chart',
  },
  {
    key: '  "direction": "up", "change_text": "',
    value: '$29.7K",',
    at: 112,
    type: 140,
    rate: 2,
    candidates: [
      { tok: '$29.7K', ok: true },
      { tok: '$29,700', ok: false },
      { tok: '$30K', ok: false },
      { tok: '29.7', ok: true },
    ],
    reason: 'figures: only text that is in the explanation',
  },
];
const REASON_KEY = '  "reason_text": "';
const PREFIX = 'the c';
const PREFIX_AT = 172; // first typed character
const PREFIX_RATE = 12;
const NEXT = { at: PREFIX_AT + PREFIX.length * PREFIX_RATE, type: PREFIX_AT + PREFIX.length * PREFIX_RATE + 26 };
const REST = 'utover to the new stack",';
const NEXT_CANDS = [
  { tok: 'utover', ok: true },
  { tok: 'ampaign', ok: false },
  { tok: 'loud', ok: false },
  { tok: 'ost', ok: false },
];
const TERMS_AT = 300;
const OUT = 358;

const typed = (f: number, start: number, rate: number, text: string): string => text.slice(0, Math.max(0, Math.min(text.length, Math.floor((f - start) / rate) + 1)));

/** Positions (line, start index) where `p` occurs in the explanation. */
const occurrences = (p: string): { line: number; i: number }[] => {
  const out: { line: number; i: number }[] = [];
  if (!p) return out;
  LINES.forEach((l, line) => {
    for (let i = l.indexOf(p); i >= 0; i = l.indexOf(p, i + 1)) out.push({ line, i });
  });
  return out;
};

const Candidates: React.FC<{ f: number; at: number; cands: { tok: string; ok: boolean }[]; reason: string; until: number }> = ({ f, at, cands, reason, until }) => {
  const o = 1 - progress(f, until - 6, 6);
  if (f < at || o <= 0) return null;
  return (
    <div style={{ position: 'absolute', left: 0, top: 0, opacity: o }}>
      {cands.map((c, i) => {
        const strike = progress(f, at + 14 + i * 3, 8);
        const chosen = c.ok ? progress(f, at + 24, 8) : 0;
        return (
          <div key={c.tok} style={{ position: 'absolute', left: PANEL.x + 28, top: PANEL.y + 62 + i * 56, height: 44, display: 'flex', alignItems: 'center', gap: 16, ...rise(f, at + i * 3, 8, 8) }}>
            <div style={{ width: 30 }}>{c.ok ? <Icon name="check" size={30} color={COLORS.paper} t={chosen} strokeScale={1.4} /> : <Icon name="cross" size={30} color={COLORS.mist} t={strike} strokeScale={1.2} />}</div>
            <span style={{ ...css('mono', MONO, c.ok ? COLORS.paper : interpolateColors(strike, [0, 1], [COLORS.paper, COLORS.mist])), position: 'relative' }}>
              {c.tok}
              {!c.ok && <span style={{ position: 'absolute', left: -4, top: '52%', height: STROKE.rule, width: `calc(${strike * 100}% + 8px)`, backgroundColor: COLORS.mist }} />}
            </span>
          </div>
        );
      })}
      <div style={{ position: 'absolute', left: PANEL.x + 28, top: PANEL.y + 62 + 4 * 56 + 6, width: PANEL.w - 56, ...css('sans', MONO, COLORS.mist), whiteSpace: 'normal', ...rise(f, at + 18, 8, 6) }}>{reason}</div>
    </div>
  );
};

export const S7Decoding: React.FC = () => {
  const f = useCurrentFrame();
  const push = mix(1, 1.02, progress(f, 0, LEN, 'standard'));
  const out = lift(f, OUT, 8, 16);
  const nTyped = Math.max(0, Math.min(PREFIX.length, Math.floor((f - PREFIX_AT) / PREFIX_RATE) + 1));
  const prefix = f >= PREFIX_AT ? PREFIX.slice(0, nTyped) : '';
  const hits = f < NEXT.type + 10 ? occurrences(prefix) : [];
  const reasonValue = prefix + (f >= NEXT.type ? typed(f, NEXT.type, 1, REST) : '');
  const caretOn = Math.floor(f / 8) % 2 === 0;

  const replyLines: { key: string; value: string; dim?: boolean; at: number }[] = [
    { key: '{"claims": [{"quote": "', value: 'Hosting rose $29.7K …",', dim: true, at: 30 },
    ...STEPS.map((s) => ({ key: s.key, value: f >= s.type ? typed(f, s.type, s.rate, s.value) : '', at: s.at - 6 })),
    { key: '  "percent_text": "", "prior_text": "", …', value: '', dim: true, at: 150 },
    { key: REASON_KEY, value: reasonValue, at: 160 },
  ];
  const activeLine = f < STEPS[1].at - 6 ? 1 : f < 160 ? 2 : f < TERMS_AT ? 4 : 5;
  const termsT = progress(f, TERMS_AT + 8, 10);

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.obsidian }}>
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${push})`, transformOrigin: '960px 900px' }}>
        <div style={{ position: 'absolute', inset: 0, ...out }}>
          <div style={{ position: 'absolute', left: 160, top: 60, ...css('sans', TYPE.title, COLORS.paper), lineHeight: 1.1, ...rise(f, 0, 12, 12) }}>Constrained decoding: admissible by construction</div>
          {/* The explanation: the only text a copied field may come from */}
          <div style={{ position: 'absolute', left: EXPL.x, top: EXPL.y, width: EXPL.w, height: 246, borderRadius: RADII.card, backgroundColor: COLORS.obsidianRaised, boxShadow: `0 0 0 1px ${COLORS.graphite}`, ...rise(f, 0, 12, 14) }}>
            <div style={{ position: 'absolute', left: 28, top: 16, display: 'flex', gap: 18 }}>
              <span style={eyebrowStyle(COLORS.mist)}>Explanation</span>
              {hits.length > 0 && (
                <span style={{ ...eyebrowStyle(COLORS.paper) }}>{`“${prefix}” could continue at ${hits.length} place${hits.length === 1 ? '' : 's'}`}</span>
              )}
            </div>
          </div>
          {hits.map((h, k) => {
            const l = LINES[h.line];
            const x = EXPL.x + 28 + measure(l.slice(0, h.i), 'sans', EXPL.size);
            const w = measure(l.slice(h.i, h.i + prefix.length), 'sans', EXPL.size);
            return <div key={`${h.line}-${h.i}-${k}`} style={{ position: 'absolute', left: x - 3, top: EXPL.top + h.line * EXPL.line - 2, width: w + 6, height: EXPL.size * 1.3 + 4, borderRadius: 6, backgroundColor: 'rgba(255,255,255,0.16)', boxShadow: `0 0 0 2px ${COLORS.paper}` }} />;
          })}
          {LINES.map((l, i) => (
            <div key={i} style={{ position: 'absolute', left: EXPL.x + 28, top: EXPL.top + i * EXPL.line, ...css('sans', EXPL.size, COLORS.paper), lineHeight: 1.3, ...rise(f, 4 + i * 3, 10, 8) }}>
              {l}
            </div>
          ))}

          {/* The reply */}
          <div style={{ position: 'absolute', left: REPLY.x, top: REPLY.y, width: REPLY.w, height: 330, borderRadius: RADII.card, backgroundColor: COLORS.obsidianRaised, boxShadow: `0 0 0 1px ${COLORS.graphite}`, ...rise(f, 24, 14, 14) }}>
            <div style={{ position: 'absolute', left: 28, top: 16, ...eyebrowStyle(COLORS.mist) }}>Reply, token by token</div>
          </div>
          {replyLines.map((r, i) => (
            <div key={i} style={{ position: 'absolute', left: REPLY.x + 28, top: REPLY.top + i * REPLY.line, height: 40, display: 'flex', alignItems: 'center', ...rise(f, r.at, 8, 6) }}>
              <span style={css('mono', MONO, r.dim ? COLORS.mist : COLORS.paper)}>{r.key}</span>
              <span style={css('mono', MONO, r.dim ? COLORS.mist : COLORS.paper)}>{r.value}</span>
              {i === activeLine && caretOn && f < TERMS_AT && <span style={{ width: CH, height: 30, backgroundColor: COLORS.paper, marginLeft: 2 }} />}
            </div>
          ))}

          {/* The mask */}
          <div style={{ position: 'absolute', left: PANEL.x, top: PANEL.y, width: PANEL.w, height: PANEL.h, borderRadius: RADII.card, boxShadow: `0 0 0 1px ${COLORS.graphite}`, ...rise(f, 40, 14, 14) }}>
            <div style={{ position: 'absolute', left: 28, top: 16, ...eyebrowStyle(COLORS.mist) }}>{f < TERMS_AT ? 'Next token · illustrative' : 'Search terms'}</div>
          </div>
          <Candidates f={f} at={STEPS[0].at} cands={STEPS[0].candidates} reason={STEPS[0].reason} until={STEPS[1].at} />
          <Candidates f={f} at={STEPS[1].at} cands={STEPS[1].candidates} reason={STEPS[1].reason} until={PREFIX_AT - 4} />
          <Candidates f={f} at={NEXT.at - 2} cands={NEXT_CANDS} reason="reason: only a continuation of a real span" until={TERMS_AT} />
          {f >= TERMS_AT && (
            <div style={{ position: 'absolute', left: PANEL.x + 28, top: PANEL.y + 66, width: PANEL.w - 56, ...rise(f, TERMS_AT + 2, 10, 8) }}>
              <div style={{ ...css('sans', TYPE.label, COLORS.paper), whiteSpace: 'normal', lineHeight: 1.3 }}>No mask. The model guesses ledger words it never sees.</div>
              <div style={{ ...css('sans', MONO, COLORS.mist), whiteSpace: 'normal', marginTop: 14, lineHeight: 1.3 }}>Constraining them to the ledger would leak the answer.</div>
            </div>
          )}

          {/* Cost, from docs/finetune.md section 6 */}
          {[
            { stat: D.maskMs, label: 'per step, for the mask', slot: 160 },
            { stat: D.unseenLeftGrammar, label: `of ${known(D.unseenCloses)} unseen closes left the grammar`, slot: 160 },
            { stat: D.unseenSecondsPerClose, label: 'per close, on the unseen suite', slot: 120 },
            { stat: D.unseenDecided, label: 'decided, as without the mask: no score moved', slot: 200 },
          ].map((b, i) => (
            <div key={i} style={{ position: 'absolute', left: 600 + i * 300, top: 784, width: 280, ...rise(f, 326 + i * 4, 10, 10) }}>
              <StatText stat={b.stat} size={TYPE.body} color={COLORS.paper} dark slot={b.slot} />
              <div style={{ ...css('sans', MONO, COLORS.mist), whiteSpace: 'normal', marginTop: 12, lineHeight: 1.25 }}>{b.label}</div>
            </div>
          ))}
        </div>
      </div>
      {/* search_terms line, carried into the unseen-worlds header (S8): the one field that benchmark tests */}
      {f >= TERMS_AT &&
        (() => {
          const t = progress(f, OUT + 9, 22, 'standard');
          const y0 = REPLY.top + 5 * REPLY.line;
          const x = mix(960 + (REPLY.x + 28 - 960) * push, TERMS_LINE.x, t);
          const y = mix(900 + (y0 - 900) * push, TERMS_LINE.y, t) - Math.sin(Math.PI * t) * 24;
          const color = COLORS.paper;
          return (
            <div style={{ position: 'absolute', left: x, top: y, height: 40, display: 'flex', alignItems: 'center', gap: 10, ...rise(f, TERMS_AT, 8, 6) }}>
              <span style={css('mono', MONO, color)}>{'"search_terms": ['}</span>
              {['migration', 'new stack'].map((w, i) => (
                <span key={w} style={{ ...css('sans', MONO, color), padding: '0 10px', lineHeight: '36px', borderRadius: 6, border: `1.5px dashed ${COLORS.mist}`, opacity: termsT > 0 ? progress(f, TERMS_AT + 10 + i * 8, 8) : 0 }}>
                  {w}
                </span>
              ))}
            </div>
          );
        })()}
    </AbsoluteFill>
  );
};
