// Scene 2 · Trust boundary (210–630), VO 2–3. The hero sentence shrinks into a model's proposal on the untrusted
// side; the parts it names are copied into fields; the reply has no verdict field. Across the boundary, admission
// checks every copied field and the ledger's own arithmetic gives the verdict.
// Principles: staging (two zones, one line between them), anticipation (fields fill before anything crosses), arcs
// (each copied field travels to admission on an arc), follow-through (the ledger rows settle into their total),
// overlapping action (rows and checks stagger by 4 frames), secondary action (slow push), timing (FAIL on beat 39).
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { COLORS, RADII, STROKE, TYPE } from '../brand/tokens';
import { Icon } from '../components/Icons';
import { Eyebrow, VerdictChip, eyebrowStyle } from '../components/ui';
import { LUMEN, usd } from '../data/cases';
import { countTo, enter, exit, lift, mix, progress, rise } from '../lib/anim';
import { TABULAR, css, fmtDate, layoutWords, measure, type WordBox } from '../lib/svg';
import { LEDGER_HEAD, LEDGER_ROWS, LEDGER_ROW_H, S1_LEDGER, S1_ORIGIN, s1Push, S1_LEN } from './S1Hook';
import { LINE1 } from './shared/console-geom';
import { HERO_LH, HERO_SIZE, PARTS, heroWords, segments } from './shared/hero';

const LEN = 420;
const T = {
  carry: 0,
  boundary: 14,
  model: 30,
  account: 112,
  amount: 130,
  reason: 148,
  terms: 172,
  never: 246,
  verdictRow: 282,
  strike: 296,
  admission: 300,
  pulses: 306,
  sum: 326,
  change: 334,
  fail: 360,
  out: 400,
} as const;

const BX = 960; // the boundary
const L = { x: 160, w: 760 } as const;
const R = { x: 1000, w: 760 } as const;
const MODEL = { y: 144, h: 164 } as const;
const PROP = { y: 326, h: 410 } as const;
const LABEL_W = 220;
const VAL_X = L.x + 28 + LABEL_W; // 408
const ROW0 = PROP.y + 62;
const QUOTE_H = 118;
const ROW_H = 42;
const rowY = (k: number): number => (k === 0 ? ROW0 : ROW0 + QUOTE_H + (k - 1) * ROW_H); // 0 quote, 1 account, 2 change, 3 reason, 4 terms, 5 verdict
const FIELD = 28;
const ADM = { y: 150, h: 222 } as const;
const LEDGER = { y: 404, w: R.w } as const;
const VERDICT_Y = 770;

// Camera: slow push anchored at the bottom centre, so content rises away from the face-cam corner.
const PUSH_O = { x: 960, y: 940 } as const;
const push = (f: number): number => mix(1, 1.025, progress(f, 0, LEN, 'standard'));

/** Word positions in three layouts, all as [x, y, scale] of a 120 px word. */
const layouts = () => {
  const a = heroWords();
  const s1 = s1Push(S1_LEN - 1);
  const toScreen = (w: WordBox) => ({ x: S1_ORIGIN.x + (w.x - S1_ORIGIN.x) * s1, y: S1_ORIGIN.y + (w.y - S1_ORIGIN.y) * s1, s: s1 });
  const words = a.map((w) => ({ text: w.text }));
  const sB = FIELD / HERO_SIZE;
  // Same three lines as the hero, so the shrinking words never cross (each line laid out on its own).
  const b = a.map((w) => {
    const line = a.filter((v) => v.line === w.line);
    const before = line.slice(0, line.indexOf(w)).map((v) => v.text).join(' ');
    const x = VAL_X + (before ? measure(`${before} `, 'sans', FIELD) : 0);
    return { x, y: rowY(0) + w.line * FIELD * 1.3, s: sB };
  });
  const sC = LINE1.size / HERO_SIZE;
  const c = layoutWords(words, 'sans', LINE1.size, LINE1.x, LINE1.y, { lineHeight: 1.3 }).map((w) => ({ x: w.x, y: w.y, s: sC }));
  return { a: a.map(toScreen), b, c, words: a };
};

/** A world point under the scene push, as screen coordinates. */
const P = (f: number, x: number, y: number) => {
  const s = push(f);
  return { x: PUSH_O.x + (x - PUSH_O.x) * s, y: PUSH_O.y + (y - PUSH_O.y) * s, s };
};

const FieldLabel: React.FC<{ y: number; text: string; struck?: number }> = ({ y, text, struck = 0 }) => (
  <div style={{ position: 'absolute', left: L.x + 28, top: y, height: 36, display: 'flex', alignItems: 'center' }}>
    <span style={{ ...css('mono', FIELD, COLORS.ash), position: 'relative' }}>
      {text}
      {struck > 0 && <span style={{ position: 'absolute', left: -4, top: '52%', width: `calc(${struck * 100}% + 8px)`, height: STROKE.rule, backgroundColor: COLORS.ink }} />}
    </span>
  </div>
);

const Quoted: React.FC<{ text: string; style?: React.CSSProperties }> = ({ text, style }) => (
  <span style={{ ...css('sans', FIELD, COLORS.ink), ...style }}>{`“${text}”`}</span>
);

export const S2Boundary: React.FC = () => {
  const f = useCurrentFrame();
  const { a, b, c, words } = layouts();
  const out = lift(f, T.out - 8, 8, 18);
  const s1Fade = 1 - exit(f, 0, 8);
  const s1 = s1Push(S1_LEN - 1);
  const marks = (() => {
    // S1's underlines and labels, at S1's last pose, leaving first.
    const hero = heroWords();
    const ids = ['account', 'amount', 'reason'] as const;
    return ids.flatMap((id) => {
      const segs = segments(hero, PARTS[id].from, PARTS[id].to);
      const last = segs[segs.length - 1];
      return [
        ...segs.map((sg, k) => (
          <div key={`${id}${k}`} style={{ position: 'absolute', left: sg.x0, top: sg.top + HERO_SIZE * 1.36, width: sg.x1 - sg.x0, height: STROKE.rule + 1, backgroundColor: COLORS.ink }} />
        )),
        <Eyebrow key={`${id}-label`} style={{ position: 'absolute', left: last.x0, top: last.top + HERO_SIZE * 1.36 + 9 }}>
          {PARTS[id].label}
        </Eyebrow>,
      ];
    });
  })();

  // Ledger card: from S1's pose (memo column leaves first) to the deterministic zone.
  const lt = progress(f, 8, 28, 'standard');
  const s1Card = { x: S1_ORIGIN.x + (S1_LEDGER.x - S1_ORIGIN.x) * s1, y: S1_ORIGIN.y + (S1_LEDGER.y - S1_ORIGIN.y) * s1, w: S1_LEDGER.w * s1 };
  const memoFade = 1 - exit(f, 0, 7);
  const sumT = progress(f, T.sum, 10);
  const change = countTo(f, T.change, T.fail - 3, 0, LUMEN.c1.change);

  // The copied parts: each field value rises in its row while its source words are underlined in the quote.
  const copy = (id: 'account' | 'amount' | 'reason', at: number) => {
    const srcText = words
      .slice(PARTS[id].from, PARTS[id].to)
      .map((w) => w.text)
      .join(' ')
      .replace(/\.$/, '');
    return { t: progress(f, at, 12), at, srcText };
  };
  const acc = copy('account', T.account);
  const amt = copy('amount', T.amount);
  const rsn = copy('reason', T.reason);
  const underline = (id: 'account' | 'amount' | 'reason', at: number) => {
    const ws = PARTS[id];
    const lines = [...new Set(words.slice(ws.from, ws.to).map((w) => w.line))];
    return lines.map((ln) => {
      const idx = Array.from({ length: ws.to - ws.from }, (_, k) => ws.from + k).filter((k) => words[k].line === ln);
      const first = b[idx[0]];
      const lastI = idx[idx.length - 1];
      const lastText = words[lastI].text.replace(/\.$/, '');
      const x1 = b[lastI].x + measure(lastText, 'sans', FIELD);
      const t = progress(f, at - 6, 10);
      return <div key={`${id}${ln}`} style={{ position: 'absolute', left: first.x, top: first.y + FIELD * 1.22, width: (x1 - first.x) * t, height: STROKE.rule, backgroundColor: COLORS.ink, opacity: 1 - progress(f, T.out - 8, 6) }} />;
    });
  };
  const terms = ['financing', 'investor', 'term sheet'];
  const proposalIn = enter(f, 4, 22);
  const labelsIn = progress(f, 30, 10);
  const neverRule = progress(f, T.never, 14);

  // Pulses: quote, change and account cross the boundary to the admission checks.
  const checks = [
    { label: 'quote is in the explanation, word for word', fromRow: 0 },
    { label: 'figures are inside the quote', fromRow: 2 },
    { label: 'an account is used only if it is on the chart', fromRow: 1 },
  ];
  const checkY = (k: number): number => ADM.y + 80 + k * 46;

  const body = (
    <div style={{ position: 'absolute', inset: 0, ...out }}>
    <div style={{ position: 'absolute', inset: 0, transform: `scale(${push(f)})`, transformOrigin: `${PUSH_O.x}px ${PUSH_O.y}px` }}>
      {/* Zones */}
      <div style={{ position: 'absolute', left: BX, top: 104, width: STROKE.rule, height: 820 * progress(f, T.boundary, 26), backgroundColor: COLORS.ink }} />
      <Eyebrow style={{ position: 'absolute', left: L.x, top: 104, ...rise(f, T.boundary + 6, 12, 8) }}>Untrusted · proposes</Eyebrow>
      <Eyebrow style={{ position: 'absolute', left: R.x, top: 104, ...rise(f, T.boundary + 10, 12, 8) }}>Deterministic · decides</Eyebrow>

      {/* The model: what it sees and what it never sees. */}
      <div
        style={{
          position: 'absolute',
          left: L.x,
          top: MODEL.y,
          width: L.w,
          height: MODEL.h,
          boxSizing: 'border-box',
          borderRadius: RADII.card,
          border: `2px dashed ${COLORS.stone}`,
          ...rise(f, T.model, 14, 16),
        }}
      >
        <div style={{ position: 'absolute', left: 26, top: 22, display: 'flex', alignItems: 'center', gap: 16 }}>
          <Icon name="chip" size={40} color={COLORS.ink} t={progress(f, T.model + 4, 14)} />
          <span style={css('sans', TYPE.ui, COLORS.ink)}>Language model</span>
        </div>
        <div style={{ position: 'absolute', left: 26, top: 84, display: 'flex', gap: 18 }}>
          <span style={{ ...css('sans', FIELD, COLORS.ash), width: 150 }}>Sees</span>
          <span style={css('sans', FIELD, COLORS.ink)}>the explanation, the chart of accounts</span>
        </div>
        <div style={{ position: 'absolute', left: 26, top: 124, display: 'flex', gap: 18 }}>
          <span style={{ ...css('sans', FIELD, COLORS.ash), width: 150 }}>Never sees</span>
          <span style={{ ...css('sans', FIELD, COLORS.ink), position: 'relative' }}>
            a transaction, vendor, memo or amount
            <span style={{ position: 'absolute', left: 0, top: FIELD * 1.28, width: `${neverRule * 100}%`, height: STROKE.rule + 1, backgroundColor: COLORS.ink }} />
          </span>
        </div>
      </div>

      {/* The proposal card (the quote's words are drawn outside the push, below). */}
      <div
        style={{
          position: 'absolute',
          left: L.x,
          top: PROP.y,
          width: L.w,
          height: PROP.h,
          borderRadius: RADII.card,
          backgroundColor: COLORS.paper,
          boxShadow: `0 0 0 1px ${COLORS.hairline}`,
          opacity: proposalIn,
          transform: `translateY(${(1 - proposalIn) * 20}px)`,
        }}
      >
        <Eyebrow style={{ position: 'absolute', left: 28, top: 18, opacity: labelsIn }}>Proposal</Eyebrow>
      </div>
      <div style={{ position: 'absolute', inset: 0, opacity: labelsIn }}>
        <FieldLabel y={rowY(0) - 2} text="quote" />
        <FieldLabel y={rowY(1)} text="account" />
        <FieldLabel y={rowY(2)} text="change" />
        <FieldLabel y={rowY(3)} text="reason" />
        <FieldLabel y={rowY(4)} text="search_terms" />
      </div>
      <div style={{ position: 'absolute', inset: 0, ...rise(f, T.verdictRow, 12, 10) }}>
        <FieldLabel y={rowY(5)} text="verdict" struck={progress(f, T.strike, 10)} />
        <div style={{ position: 'absolute', left: VAL_X, top: rowY(5), height: 36, display: 'flex', alignItems: 'center', opacity: progress(f, T.strike + 4, 10) }}>
          <span style={css('sans', FIELD, COLORS.ash)}>not in the schema</span>
        </div>
      </div>
      {/* Field values: copied from the sentence (underlined in the quote as each one lands) */}
      {underline('account', T.account)}
      {underline('amount', T.amount)}
      {underline('reason', T.reason)}
      <div style={{ position: 'absolute', left: VAL_X, top: rowY(1), height: 36, display: 'flex', alignItems: 'center', ...rise(f, acc.at, 12, 10) }}>
        <span style={css('sans', FIELD, COLORS.ink)}>{LUMEN.c1.account}</span>
      </div>
      <div style={{ position: 'absolute', left: VAL_X, top: rowY(2), height: 36, display: 'flex', alignItems: 'center', ...rise(f, amt.at, 12, 10) }}>
        <Quoted text={amt.srcText} />
      </div>
      <div style={{ position: 'absolute', left: VAL_X, top: rowY(3), height: 36, display: 'flex', alignItems: 'center', ...rise(f, rsn.at, 12, 10) }}>
        <Quoted text={LUMEN.c1.statedReason} />
      </div>
      <div style={{ position: 'absolute', left: VAL_X, top: rowY(4), height: 36, display: 'flex', alignItems: 'center', gap: 10 }}>
        {terms.map((t, i) => (
          <span
            key={t}
            style={{
              ...css('sans', FIELD, COLORS.ink),
              padding: '0 12px',
              lineHeight: '34px',
              borderRadius: RADII.control,
              border: `1.5px dashed ${COLORS.ash}`,
              ...rise(f, T.terms + i * 8, 10, 8),
            }}
          >
            {t}
          </span>
        ))}
      </div>

      {/* Admission */}
      <div
        style={{
          position: 'absolute',
          left: R.x,
          top: ADM.y,
          width: R.w,
          height: ADM.h,
          borderRadius: RADII.card,
          backgroundColor: COLORS.paper,
          boxShadow: `0 0 0 1px ${COLORS.hairline}`,
          ...rise(f, T.admission - 10, 12, 14),
        }}
      >
        <div style={{ position: 'absolute', left: 28, top: 22, display: 'flex', alignItems: 'baseline', gap: 14 }}>
          <span style={css('sans', TYPE.ui, COLORS.ink)}>Admission</span>
          <span style={css('mono', FIELD, COLORS.ash)}>admit()</span>
        </div>
      </div>
      {checks.map((c, k) => {
        const arrive = T.pulses + k * 5 + 14;
        return (
          <div key={c.label} style={{ position: 'absolute', left: R.x + 28, top: checkY(k), height: 36, display: 'flex', alignItems: 'center', gap: 14, ...rise(f, T.admission - 6 + k * 3, 10, 8) }}>
            <Icon name="check" size={30} color={COLORS.ink} t={progress(f, arrive, 8)} strokeScale={1.3} />
            <span style={css('sans', FIELD, COLORS.ink)}>{c.label}</span>
          </div>
        );
      })}
      {checks.map((c, k) => {
        const t = progress(f, T.pulses + k * 5, 14, 'standard');
        if (t <= 0 || t >= 1) return null;
        const x0 = L.x + L.w - 20;
        const y0 = rowY(c.fromRow) + 18;
        const x1 = R.x + 43;
        const y1 = checkY(k) + 18;
        const x = mix(x0, x1, t);
        const y = mix(y0, y1, t) - Math.sin(Math.PI * t) * 60;
        return <div key={k} style={{ position: 'absolute', left: x - 7, top: y - 7, width: 14, height: 14, borderRadius: 7, backgroundColor: COLORS.ink }} />;
      })}

      {/* Verdict */}
      <div style={{ position: 'absolute', left: R.x, top: VERDICT_Y, ...rise(f, T.fail, 9, 10) }}>
        <VerdictChip verdict="FAIL" size={32} t={progress(f, T.fail + 2, 9)} />
      </div>
      <div style={{ position: 'absolute', left: R.x, top: VERDICT_Y + 70, ...rise(f, T.fail + 5, 12, 10) }}>
        <span style={css('sans', TYPE.label, COLORS.ink)}>{LUMEN.c1.reason}</span>
      </div>
    </div>
    </div>
  );

  // Ledger card, outside the push until it has landed (then it rides the push like everything else).
  const ledger = (() => {
    const pos = P(f, R.x, LEDGER.y);
    const x = mix(s1Card.x, pos.x, lt);
    const y = mix(s1Card.y, pos.y, lt);
    const w = mix(s1Card.w, LEDGER.w * pos.s, lt);
    const sc = mix(s1, pos.s, lt);
    const rowsH = LEDGER_ROWS.length * LEDGER_ROW_H;
    const totals = [
      { label: 'Oct 2026', value: usd(LUMEN.c1.current) },
      { label: 'Sep 2026', value: usd(LUMEN.c1.prior) },
    ];
    const h = (LEDGER_HEAD + rowsH + 12 + sumT * (3 * 44 + 18)) * sc;
    return (
      <div style={{ position: 'absolute', left: x, top: y, width: w, height: h, borderRadius: 16, backgroundColor: COLORS.paper, boxShadow: `0 0 0 1px ${COLORS.hairline}`, overflow: 'hidden', ...out }}>
        <div style={{ position: 'absolute', left: 0, top: 0, width: w / sc, transform: `scale(${sc})`, transformOrigin: '0 0' }}>
          <div style={{ position: 'absolute', left: 28, top: 18, ...eyebrowStyle(COLORS.ash), whiteSpace: 'nowrap' }}>
            <span style={{ opacity: memoFade }}>Ledger · Legal · Oct 2026</span>
            <span style={{ position: 'absolute', left: 0, opacity: progress(f, 10, 10) }}>Ledger · {LUMEN.c1.account}</span>
          </div>
          {LEDGER_ROWS.map((r) => {
            const i = LEDGER_ROWS.indexOf(r);
            return (
              <div
                key={r.id}
                style={{
                  position: 'absolute',
                  left: 28,
                  width: w / sc - 56,
                  top: LEDGER_HEAD + i * LEDGER_ROW_H,
                  height: LEDGER_ROW_H,
                  display: 'flex',
                  alignItems: 'center',
                  gap: 20,
                  borderTop: `1px solid ${COLORS.hairline}`,
                  opacity: mix(1, 0.55, sumT),
                }}
              >
                <span style={css('mono', TYPE.eyebrow, COLORS.ash)}>{r.id}</span>
                <span style={{ ...css('sans', TYPE.eyebrow, COLORS.ash), ...TABULAR, opacity: progress(f, 8, 8) }}>{fmtDate(r.date)}</span>
                <span style={{ ...css('sans', TYPE.eyebrow, COLORS.ink), position: 'absolute', left: 140, opacity: memoFade }}>{r.memo}</span>
                <span style={{ flex: 1 }} />
                <span style={{ ...css('sans', TYPE.eyebrow, COLORS.ink), ...TABULAR }}>{usd(r.amount)}</span>
              </div>
            );
          })}
          <div style={{ position: 'absolute', left: 28, width: w / sc - 56, top: LEDGER_HEAD + rowsH + 8, height: STROKE.rule, backgroundColor: COLORS.ink, transform: `scaleX(${sumT})`, transformOrigin: '100% 50%' }} />
          {totals.map((tt, k) => (
            <div key={tt.label} style={{ position: 'absolute', left: 28, width: w / sc - 56, top: LEDGER_HEAD + rowsH + 18 + k * 44, height: 44, display: 'flex', alignItems: 'center', ...rise(f, T.sum + 4 + k * 4, 10, 8) }}>
              <span style={css('sans', TYPE.eyebrow, COLORS.ash)}>{tt.label}</span>
              <span style={{ flex: 1 }} />
              <span style={{ ...css('sans', TYPE.eyebrow, COLORS.ink), ...TABULAR }}>{tt.value}</span>
            </div>
          ))}
          <div style={{ position: 'absolute', left: 28, width: w / sc - 56, top: LEDGER_HEAD + rowsH + 18 + 2 * 44, height: 50, display: 'flex', alignItems: 'center', ...rise(f, T.change, 10, 8) }}>
            <span style={css('sans', TYPE.label, COLORS.ink)}>Change</span>
            <span style={{ flex: 1 }} />
            <span style={{ ...css('sans', TYPE.label, COLORS.ink), ...TABULAR }}>{usd(change, { sign: true })}</span>
          </div>
        </div>
      </div>
    );
  })();

  // The sentence's words: S1 layout → quote field → (carry out) the first line of the console's explanation pane.
  const wordsEl = words.map((w, i) => {
    const t1 = progress(f, T.carry, 28, 'standard');
    // Out: first slide each line sideways to its final x (lines stay stacked), then close the lines up.
    const t3 = progress(f, T.out, 12, 'standard');
    const t3y = progress(f, T.out + 5, 13, 'standard');
    const bScreen = P(f, b[i].x, b[i].y);
    const ab = { x: mix(a[i].x, bScreen.x, t1), y: mix(a[i].y, bScreen.y, t1), s: mix(a[i].s, b[i].s * bScreen.s, t1) };
    const x = mix(ab.x, c[i].x, t3);
    const y = mix(ab.y, c[i].y, t3y);
    const s = mix(ab.s, c[i].s, t3);
    // Line height shrinks with the move: 1.45 at headline size, 1.3 in the field.
    return (
      <div
        key={i}
        style={{
          position: 'absolute',
          left: x,
          top: y,
          ...css('sans', HERO_SIZE, COLORS.ink),
          letterSpacing: `${mix(-0.02, -0.005, t1)}em`,
          lineHeight: mix(HERO_LH, 1.3, t1),
          transform: `scale(${s})`,
          transformOrigin: '0 0',
        }}
      >
        {w.text}
      </div>
    );
  });

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bone }}>
      {body}
      {ledger}
      {wordsEl}
      {s1Fade > 0 && (
        <div style={{ position: 'absolute', inset: 0, opacity: s1Fade, transform: `scale(${s1})`, transformOrigin: `${S1_ORIGIN.x}px ${S1_ORIGIN.y}px` }}>
          {marks}
          <Eyebrow style={{ position: 'absolute', left: 160, top: 110 }}>{`${LUMEN.entity} · October 2026 close · operating expense commentary`}</Eyebrow>
        </div>
      )}
    </AbsoluteFill>
  );
};

export const S2_WIDTH_CHECK = (): number => measure(LUMEN.c1.quote, 'sans', LINE1.size);
