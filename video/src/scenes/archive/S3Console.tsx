// Scene 3 · Console walkthrough (630–1410), VO 4–6. The carried sentence becomes the first line of a pasted
// commentary; Verify gives every claim a verdict; the Legal claim's working shows why it fails. On a second close a
// model's search word is the only support, so the claim waits; the reviewer teaches it through the safety gate. On a
// third close the rules decide the same reason alone.
// Every value on screen is the real checker's output for these fictional closes (src/data/cases.ts); coverage
// counts come from src/data/results.ts.
// Principles: staging (one region of the console changes at a time), anticipation (buttons press before results),
// follow-through (rows and underlines settle in staggered order), slow in / slow out, overlapping action (content
// swaps lead the chrome by 4–8 frames), secondary action (slow push), arcs (the confirmed term and the lesson travel on
// arcs), timing (verdict and count hits on beats).
import { AbsoluteFill, useCurrentFrame } from 'remotion';
import { COLORS, RADII, STROKE, TYPE } from '../brand/tokens';
import { BrowserFrame, Button, SelectBox, Sidebar, Swap, TermChip, TopBar, UI, UI_L } from '../components/Console';
import { Highlight } from '../components/Highlight';
import { Icon } from '../components/Icons';
import { Eyebrow, VerdictChip, eyebrowStyle, verdictColor } from '../components/ui';
import { BRIGHTFIELD, COBALT, LUMEN, usd, type Verdict } from '../data/cases';
import { RESULTS, known } from '../data/results';
import { countTo, ease, enter, lift, mix, progress, rise } from '../lib/anim';
import { TABULAR, css, measure } from '../lib/svg';
import { COVERAGE, DETAIL, EXPL, EXPL_TEXT_X, HEAD, LIST, MAIN, PANE_PAD, SPLIT } from './shared/console-geom';
import { LESSON_PILL } from './shared/loop-geom';

const LEN = 780;
const T = {
  chrome: 2,
  paste: 30,
  verify: 52,
  underline: 64,
  counts: 66,
  countsEnd: 105,
  toClaims: 165,
  detail: 178,
  recon: 196,
  finding: 236,
  misbook: 290,
  toB: 345,
  verifyB: 360,
  detailB: 372,
  teach: 450,
  typing: 470,
  gatePress: 506,
  gate: 514,
  recordPress: 562,
  pass: 570,
  toC: 612,
  verifyC: 618,
  detailC: 622,
  noModel: 676,
  out: 734,
} as const;

const PUSH_O = { x: 1816, y: 540 } as const;
const push = (f: number): number => mix(1, 1.035, progress(f, 0, LEN, 'standard'));

type Phase = 'lumen' | 'bright' | 'cobalt';
const phaseAt = (f: number): Phase => (f < T.toB ? 'lumen' : f < T.toC ? 'bright' : 'cobalt');

/** 0 → 1 → 0 press curve for a button pressed at `at`. */
const press = (f: number, at: number): number => (f >= at && f < at + 8 ? (f - at) / 8 : 0);

// ── Explanation pane (before the switch to Claims) ──────────────────────────────────────────────────────────────
const ExplanationPane: React.FC<{ f: number; splitY: number }> = ({ f, splitY }) => {
  const sentences = LUMEN.sentences;
  const out = 1 - progress(f, T.toClaims, 12);
  return (
    <div style={{ position: 'absolute', left: 0, top: 0, opacity: out }}>
      {sentences.map((s, i) => {
        const y = EXPL.top + (splitY - SPLIT.y) + i * EXPL.line;
        const ul = progress(f, T.underline + i * 5, 12);
        const w = measure(s.text, 'sans', EXPL.size);
        const appear = i === 0 ? { opacity: 1, transform: 'none' } : rise(f, T.paste + i * 2, 8, 8);
        return (
          <div key={s.tag}>
            {/* Line 1 is drawn by the carried words for the first frames, then by this element (same place, same size). */}
            <div style={{ position: 'absolute', left: EXPL_TEXT_X, top: y, ...css('sans', EXPL.size, COLORS.ink), lineHeight: 1.3, ...appear, opacity: i === 0 ? 1 : appear.opacity }}>{s.text}</div>
            <div style={{ position: 'absolute', left: EXPL_TEXT_X, top: y + EXPL.size * 1.3 + 1, width: w * ul, height: 4, borderRadius: 2, backgroundColor: verdictColor(s.verdict) }} />
            <div style={{ position: 'absolute', left: EXPL.tagX, top: y, height: EXPL.size * 1.3, display: 'flex', alignItems: 'center', ...rise(f, T.underline + i * 5 + 4, 8, 6) }}>
              <span style={css('mono', UI, COLORS.ash)}>{s.tag}</span>
            </div>
          </div>
        );
      })}
      <div style={{ position: 'absolute', left: EXPL_TEXT_X, top: EXPL.top + (splitY - SPLIT.y) + sentences.length * EXPL.line + 4, ...rise(f, T.paste + 16, 8, 8) }}>
        <span style={css('sans', UI, COLORS.ash)}>+ 3 more sentences (not shown here)</span>
      </div>
      {/* Paste caret, a step function: blinks every 8 frames until Verify. */}
      {f >= T.paste + 16 && f < T.verify && Math.floor((f - T.paste) / 8) % 2 === 0 && (
        <div style={{ position: 'absolute', left: EXPL_TEXT_X + measure(sentences[sentences.length - 1].text, 'sans', EXPL.size) + 6, top: EXPL.top + (sentences.length - 1) * EXPL.line + 4, width: 3, height: 34, backgroundColor: COLORS.ink }} />
      )}
    </div>
  );
};

// ── Claims list ──────────────────────────────────────────────────────────────────────────────────────────────────
interface Row {
  tag: string;
  verdict: Verdict;
  account: string;
  quote?: string;
}

const ROW_H = 54;

const ClaimsList: React.FC<{ f: number; rows: Row[]; at: number; splitY: number; selectedQuote?: string }> = ({ f, rows, at, splitY, selectedQuote }) => {
  let y = splitY + 84;
  return (
    <>
      {rows.map((r, i) => {
        const top = y;
        const sel = i === 0;
        const h = sel && selectedQuote ? ROW_H + 80 : ROW_H;
        y += h;
        return (
          <div key={`${r.tag}-${i}`} style={{ position: 'absolute', left: LIST.x + 1, top, width: LIST.w - 2, height: h, backgroundColor: sel ? COLORS.surface : 'transparent', borderTop: `1px solid ${COLORS.hairline}`, ...rise(f, at + i * 4, 10, 10) }}>
            <div style={{ position: 'absolute', left: 26, top: 9, display: 'flex', alignItems: 'center', gap: 14 }}>
              <VerdictChip verdict={r.verdict} size={UI} t={progress(f, at + i * 4 + 4, 8)} />
              <span style={css('mono', UI, COLORS.ash)}>{r.tag}</span>
              <span style={css('sans', UI, COLORS.ink)}>{r.account}</span>
            </div>
            {sel && selectedQuote && (
              <div style={{ position: 'absolute', left: 26, top: 58, width: LIST.w - 60, ...css('sans', UI, COLORS.ink), whiteSpace: 'normal', lineHeight: 1.3 }}>{selectedQuote}</div>
            )}
          </div>
        );
      })}
    </>
  );
};

// ── Detail pane bodies ──────────────────────────────────────────────────────────────────────────────────────────
const DX = DETAIL.x + PANE_PAD;
const DW = DETAIL.w - PANE_PAD * 2;

const KV: React.FC<{ y: number; k: string; children: React.ReactNode; style?: React.CSSProperties }> = ({ y, k, children, style }) => (
  <div style={{ position: 'absolute', left: DX, top: y, width: DW, display: 'flex', alignItems: 'center', minHeight: 40, ...style }}>
    <span style={{ ...css('sans', UI, COLORS.ash), width: 210, flex: 'none' }}>{k}</span>
    <span style={{ display: 'flex', alignItems: 'center', gap: 10 }}>{children}</span>
  </div>
);

const TxRow: React.FC<{ y: number; id: string; memo: React.ReactNode; amount: string; style?: React.CSSProperties }> = ({ y, id, memo, amount, style }) => (
  <div style={{ position: 'absolute', left: DX, top: y, width: DW, height: 44, display: 'flex', alignItems: 'center', gap: 16, borderTop: `1px solid ${COLORS.hairline}`, ...style }}>
    <span style={css('mono', UI, COLORS.ash)}>{id}</span>
    <span style={{ ...css('sans', UI, COLORS.ink), flex: 1, display: 'flex' }}>{memo}</span>
    <span style={{ ...css('sans', UI, COLORS.ink), ...TABULAR }}>{amount}</span>
  </div>
);

/** A memo with one word highlighted (model guess: dashed outline; learned: chartreuse swipe). */
const Memo: React.FC<{ memo: string; word: string; kind: 'model' | 'learned'; t: number; seed: string }> = ({ memo, word, kind, t, seed }) => {
  const i = memo.toLowerCase().indexOf(word);
  if (i < 0) return <span>{memo}</span>;
  const pre = memo.slice(0, i);
  const hit = memo.slice(i, i + word.length);
  const post = memo.slice(i + word.length);
  const x = measure(pre, 'sans', UI);
  const w = measure(hit, 'sans', UI);
  return (
    <span style={{ position: 'relative', whiteSpace: 'pre' }}>
      {kind === 'learned' ? (
        <Highlight x={x - 3} y={6} width={w + 6} height={30} t={t} seed={seed} />
      ) : (
        <span style={{ position: 'absolute', left: x - 5, top: 2, width: (w + 10) * t, height: 38, boxSizing: 'border-box', border: `1.5px dashed ${COLORS.ash}`, borderRadius: 6, opacity: t > 0 ? 1 : 0 }} />
      )}
      <span style={{ position: 'relative' }}>{pre}</span>
      <span style={{ position: 'relative' }}>{hit}</span>
      <span style={{ position: 'relative' }}>{post}</span>
    </span>
  );
};

/** A wrapped reason line in the detail pane (two lines at most at UI_L). */
const Reason: React.FC<{ y: number; children: React.ReactNode; style?: React.CSSProperties }> = ({ y, children, style }) => (
  <div style={{ position: 'absolute', left: DX, top: y, width: DW, ...css('sans', UI_L, COLORS.ink), whiteSpace: 'normal', lineHeight: 1.3, ...style }}>{children}</div>
);

const LumenDetail: React.FC<{ f: number; top: number }> = ({ f, top }) => {
  const c = LUMEN.c1;
  const r = (k: number) => rise(f, T.recon + k * 4, 10, 8);
  return (
    <>
      <Reason y={top + 80} style={rise(f, T.detail + 2, 10, 10)}>
        {c.reason}
      </Reason>
      <div style={{ position: 'absolute', left: DX, top: top + 136, ...rise(f, T.detail + 6, 10, 8) }}>
        <VerdictChip verdict="FAIL" size={UI} t={progress(f, T.detail + 8, 9)} />
      </div>
      <Eyebrow style={{ position: 'absolute', left: DX, top: top + 204, ...r(0) }}>Reconstruction</Eyebrow>
      <KV y={top + 240} k="Ledger" style={r(1)}>
        <span style={{ ...css('sans', UI, COLORS.ink), ...TABULAR }}>{`Sep ${usd(c.prior)} → Oct ${usd(c.current)} · ${usd(c.change, { sign: true })}`}</span>
      </KV>
      <KV y={top + 284} k="Stated" style={r(2)}>
        <span style={css('sans', UI, COLORS.ink)}>{`rose, change ${c.stated}`}</span>
      </KV>
      <KV y={top + 328} k="Reason" style={r(3)}>
        <span style={css('sans', UI, COLORS.ink)}>{`“${c.statedReason}”`}</span>
      </KV>
      <div style={{ position: 'absolute', left: DX, top: top + 394, display: 'flex', alignItems: 'center', gap: 16, ...rise(f, T.finding, 10, 8) }}>
        <span style={eyebrowStyle()}>Findings</span>
        <span style={{ ...eyebrowStyle(COLORS.partialInk), backgroundColor: COLORS.partialTint, padding: '4px 12px', borderRadius: 6 }}>Possible misclassification</span>
      </div>
      <div style={{ position: 'absolute', left: DX, top: top + 440, width: DW, height: 44, display: 'flex', alignItems: 'center', gap: 16, borderTop: `1px solid ${COLORS.hairline}`, ...rise(f, T.finding + 6, 10, 8) }}>
        <span style={css('mono', UI, COLORS.ash)}>{c.misbooked.id}</span>
        <span style={css('sans', UI, COLORS.ink)}>{c.misbooked.memo}</span>
      </div>
      <div style={{ position: 'absolute', left: DX, top: top + 490, display: 'flex', alignItems: 'center', gap: 12, ...rise(f, T.misbook, 10, 8) }}>
        <span style={{ ...css('sans', UI, COLORS.ink), ...TABULAR }}>{usd(c.misbooked.amount)}</span>
        <span style={css('sans', UI, COLORS.ash)}>booked to</span>
        <span style={{ ...css('sans', UI, COLORS.ink), position: 'relative' }}>
          {c.misbooked.account}
          <span style={{ position: 'absolute', left: 0, top: 38, height: STROKE.rule + 1, width: `${progress(f, T.misbook + 6, 12) * 100}%`, backgroundColor: COLORS.partial }} />
        </span>
      </div>
      <KV y={top + 548} k="If reclassified" style={rise(f, T.misbook + 14, 10, 8)}>
        <span style={{ ...css('sans', UI_L, COLORS.ink), ...TABULAR }}>{usd(c.reclassified, { sign: true })}</span>
        <span style={css('sans', UI, COLORS.ash)}>agrees with the stated $90K</span>
      </KV>
    </>
  );
};

const BrightDetail: React.FC<{ f: number; top: number }> = ({ f, top }) => {
  const c = BRIGHTFIELD.c1;
  const passOut = progress(f, T.pass, 4);
  const passT = progress(f, T.pass + 4, 8);
  const teachIn = progress(f, T.teach + 12, 12);
  const searchedOut = lift(f, T.teach - 8, 8, 14);
  // The model's matched term flies from its chip into the form's terms field, once the other chips have gone:
  // right, clear of the form's first field, then down, then left into the second field.
  const fly = progress(f, T.teach + 4, 30);
  const Y = { chip: 178, searched: 240, chips: 276, matched: 384, rows: 420, teach: 240, l1: 276, in1: 310, l2: 372, in2: 406, buttons: 470, gate: 534 };
  // Chip positions: chips flow left to right and wrap at DW (10 px gaps, 24 px padding).
  const chipW = (w: string) => measure(w, 'sans', UI) + 24 + 3;
  const flow = [...c.written, ...c.model];
  let cx = 0;
  let cy = 0;
  const at: Record<string, { x: number; y: number }> = {};
  for (const w of flow) {
    if (cx > 0 && cx + chipW(w) > DW) {
      cx = 0;
      cy += 50;
    }
    at[w] = { x: cx, y: cy };
    cx += chipW(w) + 10;
  }
  return (
    <>
      <Reason y={top + 80} style={rise(f, T.detailB + 2, 10, 10)}>
        <span style={{ opacity: 1 - progress(f, T.pass, 8) }}>{c.reasonBefore}</span>
      </Reason>
      <Reason y={top + 80} style={{ opacity: progress(f, T.pass + 4, 8) }}>
        {c.reasonAfter}
      </Reason>
      <div style={{ position: 'absolute', left: DX, top: top + Y.chip, display: 'flex', gap: 14, alignItems: 'center', ...rise(f, T.detailB + 6, 10, 8) }}>
        <div style={{ position: 'relative' }}>
          <div style={{ opacity: 1 - passOut }}>
            <VerdictChip verdict="REVIEW" size={UI} t={progress(f, T.detailB + 8, 9)} />
          </div>
          <div style={{ position: 'absolute', left: 0, top: 0, opacity: passT, transform: `translateY(${(1 - passT) * 6}px)` }}>
            <VerdictChip verdict="PASS" size={UI} t={progress(f, T.pass + 2, 9)} />
          </div>
        </div>
        <span style={{ ...css('sans', UI, COLORS.ash), opacity: 1 - passOut }}>Support rests on model terms</span>
      </div>
      {/* Searched + matched, until the teach form takes their place. */}
      <div style={{ position: 'absolute', left: 0, top: 0, ...searchedOut }}>
        <div style={{ position: 'absolute', left: DX, top: top + Y.searched, display: 'flex', gap: 16, alignItems: 'center', ...rise(f, T.detailB + 10, 10, 8) }}>
          <span style={eyebrowStyle()}>Searched</span>
          <span style={css('sans', UI, COLORS.ash)}>written · model (dashed)</span>
        </div>
        {flow.map((w, i) => {
          const kind = c.written.includes(w as never) ? 'written' : 'model';
          const st = rise(f, T.detailB + 12 + i * 2, 8, 6);
          return (
            <div key={w} style={{ position: 'absolute', left: DX + at[w].x, top: top + Y.chips + at[w].y, ...st, opacity: w === c.matchedTerm && fly > 0 ? 0 : st.opacity }}>
              <TermChip text={w} kind={kind} />
            </div>
          );
        })}
        <Eyebrow style={{ position: 'absolute', left: DX, top: top + Y.matched, ...rise(f, T.detailB + 30, 10, 8) }}>Matched by the model's word</Eyebrow>
        {c.matched.map((m, i) => (
          <TxRow
            key={m.id}
            y={top + Y.rows + i * 46}
            id={m.id}
            memo={<Memo memo={m.memo} word={c.matchedTerm} kind="model" t={progress(f, T.detailB + 40 + i * 4, 10)} seed={`b${i}`} />}
            amount={usd(Math.round(m.amount))}
            style={rise(f, T.detailB + 32 + i * 4, 10, 8)}
          />
        ))}
      </div>
      {/* Teach Proven */}
      {teachIn > 0 && (
        <div style={{ position: 'absolute', left: 0, top: 0, opacity: teachIn, transform: `translateY(${(1 - teachIn) * 16}px)` }}>
          <Eyebrow style={{ position: 'absolute', left: DX, top: top + Y.teach }}>Teach Proven</Eyebrow>
          <div style={{ position: 'absolute', left: DX, top: top + Y.l1, ...css('sans', UI, COLORS.ash) }}>When the stated reason says</div>
          <div style={{ position: 'absolute', left: DX, top: top + Y.in1, width: DW, height: 50, borderRadius: RADII.control, boxShadow: `inset 0 0 0 1px ${COLORS.hairline}`, display: 'flex', alignItems: 'center', padding: '0 16px', boxSizing: 'border-box' }}>
            <span style={css('sans', UI, COLORS.ink)}>{c.driver}</span>
          </div>
          <div style={{ position: 'absolute', left: DX, top: top + Y.l2, ...css('sans', UI, COLORS.ash) }}>search the ledger for</div>
          <div style={{ position: 'absolute', left: DX, top: top + Y.in2, width: DW, height: 50, borderRadius: RADII.control, boxShadow: `inset 0 0 0 1px ${COLORS.hairline}` }} />
          <div style={{ position: 'absolute', left: DX, top: top + Y.buttons, display: 'flex', gap: 14 }}>
            <Button label="Check with the safety gate" press={press(f, T.gatePress)} size={30} h={50} />
            <Button label="Record" press={press(f, T.recordPress)} size={30} h={50} />
          </div>
          <div style={{ position: 'absolute', left: DX, top: top + Y.gate, width: DW, ...rise(f, T.gate, 10, 8) }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: 12 }}>
              <span style={{ ...css('sans', UI, COLORS.ink, 500), backgroundColor: COLORS.chartreuse, padding: '2px 10px', borderRadius: 6 }}>Gate: safe</span>
              <span style={css('sans', UI, COLORS.ink)}>This claim: REVIEW → PASS.</span>
            </div>
            <div style={{ ...css('sans', UI, COLORS.ash), marginTop: 8, whiteSpace: 'normal', lineHeight: 1.3 }}>{BRIGHTFIELD.gateLine}</div>
          </div>
        </div>
      )}
      {/* The confirmed word: model chip (dashed) → the form's field → learned (chartreuse) once recorded. */}
      {fly > 0 &&
        (() => {
          const from = at[c.matchedTerm];
          const x0 = DX + from.x;
          const y0 = top + Y.chips + from.y;
          const xr = DX + 540;
          const y1 = top + Y.in2 + 5;
          const s1 = Math.min(1, fly / 0.35);
          const s2 = Math.max(0, Math.min(1, (fly - 0.35) / 0.35));
          const s3 = Math.max(0, Math.min(1, (fly - 0.7) / 0.3));
          const x = s3 > 0 ? mix(xr, DX + 6, ease.standard(s3)) : mix(x0, xr, ease.standard(s1));
          const y = mix(y0, y1, ease.standard(s2));
          const learned = progress(f, T.pass, 8);
          return (
            <div style={{ position: 'absolute', left: x, top: y }}>
              <TermChip text={c.matchedTerm} kind="model" style={{ backgroundColor: `rgba(228,242,34,${learned})`, borderColor: learned > 0.5 ? 'transparent' : COLORS.ash }} />
            </div>
          );
        })()}
    </>
  );
};

const CobaltDetail: React.FC<{ f: number; top: number }> = ({ f, top }) => {
  const c = COBALT.c1;
  return (
    <>
      <Reason y={top + 80} style={rise(f, T.detailC + 2, 10, 10)}>
        {BRIGHTFIELD.c1.reasonAfter}
      </Reason>
      <div style={{ position: 'absolute', left: DX, top: top + 178, display: 'flex', gap: 14, alignItems: 'center', ...rise(f, T.detailC + 6, 10, 8) }}>
        <VerdictChip verdict="PASS" size={UI} t={progress(f, T.detailC + 8, 9)} />
        <span style={css('sans', UI, COLORS.ash)}>{`Extractor: ${COBALT.extractor}`}</span>
      </div>
      <div style={{ position: 'absolute', left: DX, top: top + 244, display: 'flex', gap: 16, alignItems: 'center', ...rise(f, T.detailC + 10, 10, 8) }}>
        <span style={eyebrowStyle()}>Searched</span>
        <TermChip text={BRIGHTFIELD.lesson.terms[0]} kind="learned" />
        <span style={css('sans', UI, COLORS.ash)}>learned</span>
      </div>
      <Eyebrow style={{ position: 'absolute', left: DX, top: top + 314, ...rise(f, T.detailC + 16, 10, 8) }}>Matched</Eyebrow>
      {c.matched.map((m, i) => (
        <TxRow
          key={m.id}
          y={top + 350 + i * 46}
          id={m.id}
          memo={<Memo memo={m.memo} word={BRIGHTFIELD.lesson.terms[0]} kind="learned" t={progress(f, T.detailC + 26 + i * 5, 12)} seed={`c${i}`} />}
          amount={usd(Math.round(m.amount))}
          style={rise(f, T.detailC + 18 + i * 4, 10, 8)}
        />
      ))}
      <div style={{ position: 'absolute', left: DX, top: top + 474, width: DW, height: 116, borderRadius: RADII.ui, backgroundColor: COLORS.bone, ...rise(f, T.noModel, 12, 12) }}>
        <div style={{ position: 'absolute', left: 24, top: 18, display: 'flex', alignItems: 'center', gap: 14 }}>
          <Icon name="chip" size={34} color={COLORS.ash} t={progress(f, T.noModel + 4, 12)} />
          <span style={css('sans', UI_L, COLORS.ink)}>No model ran. The lesson bound the reason.</span>
        </div>
        <div style={{ position: 'absolute', left: 24, top: 66, ...css('sans', UI, COLORS.ash) }}>{`“${BRIGHTFIELD.lesson.trigger}” → ${BRIGHTFIELD.lesson.terms[0]}`}</div>
      </div>
    </>
  );
};

/** The confirmed lesson, as the pill that travels into the loop diagram (two lines). */
export const LessonText: React.FC = () => (
  <div style={{ ...css('sans', UI, COLORS.ink), whiteSpace: 'normal', lineHeight: 1.25 }}>
    {`“${BRIGHTFIELD.lesson.trigger}”`}
    <br />
    {`→ ${BRIGHTFIELD.lesson.terms[0]}`}
  </div>
);

// ── The scene ────────────────────────────────────────────────────────────────────────────────────────────────────
export const S3Console: React.FC = () => {
  const f = useCurrentFrame();
  const phase = phaseAt(f);
  const out = lift(f, T.out, 10, 6);
  const chromeIn = (k: number) => rise(f, T.chrome + k * 3, 14, 14);
  const fold = progress(f, T.toClaims, 20, 'standard');
  const splitY = mix(SPLIT.y, SPLIT.yFolded, fold);
  const toB = progress(f, T.toB, 14);
  const toC = progress(f, T.toC, 14);
  const learned = f >= T.pass + 6 ? 1 : 0;
  const learnedPop = progress(f, T.pass + 6, 8);

  const closeName = (
    <span style={{ position: 'relative', display: 'inline-flex' }}>
      <Swap a={phase === 'cobalt' ? BRIGHTFIELD.close : LUMEN.close} b={phase === 'cobalt' ? COBALT.close : BRIGHTFIELD.close} t={phase === 'lumen' ? 0 : phase === 'bright' ? toB : toC} style={css('sans', UI, COLORS.ink)} />
    </span>
  );
  const titleT = phase === 'lumen' ? 0 : phase === 'bright' ? toB : toC;
  const titleA = phase === 'cobalt' ? BRIGHTFIELD.close : LUMEN.close;
  const titleB = phase === 'cobalt' ? COBALT.close : BRIGHTFIELD.close;
  const extA = phase === 'cobalt' ? BRIGHTFIELD.extractor : 'Rules (offline)';
  const extB = phase === 'cobalt' ? COBALT.extractor : BRIGHTFIELD.extractor;
  const extT = phase === 'lumen' ? 0 : progress(f, phase === 'bright' ? T.toB + 6 : T.toC + 6, 12);
  const metaA = phase === 'cobalt' ? 'claude/0.2 · verifier 0.1 · text and chart only' : 'rules/0.1 · verifier 0.1 · nothing left this machine';
  const metaB = phase === 'cobalt' ? 'rules/0.1 · verifier 0.1 · nothing left this machine' : 'claude/0.2 · verifier 0.1 · text and chart only';

  // Coverage (Lumen, README numbers), folding away when the list opens.
  const cov = RESULTS.showcase;
  const covOut = 1 - progress(f, T.toClaims - 4, 12);
  const covCols = [
    { label: 'Claims checked', value: String(countTo(f, T.counts, T.countsEnd, 0, cov.claims.value ?? 0)), sub: `of ${known(cov.withFigures)} with figures`, dot: undefined },
    { label: 'Pass', value: String(countTo(f, T.counts + 3, T.countsEnd, 0, cov.pass.value ?? 0)), sub: '', dot: COLORS.chartreuse },
    { label: 'Fail', value: String(countTo(f, T.counts + 6, T.countsEnd, 0, cov.fail.value ?? 0)), sub: '', dot: COLORS.flag },
    { label: 'Need review', value: String(countTo(f, T.counts + 9, T.countsEnd, 0, cov.review.value ?? 0)), sub: `+${known(cov.notExtracted)} not extracted`, dot: COLORS.partial },
    { label: 'Decided', value: `${(Math.round(mix(0, cov.decided.value ?? 0, progress(f, T.counts + 12, T.countsEnd - T.counts - 12)) * 10) / 10).toFixed(1)}%`, sub: '7 of 9', dot: undefined },
  ];
  const bar = [
    { n: cov.pass.value ?? 0, c: COLORS.chartreuse },
    { n: cov.fail.value ?? 0, c: COLORS.flag },
    { n: cov.review.value ?? 0, c: COLORS.partial },
    { n: cov.notExtracted.value ?? 0, c: COLORS.stone },
  ];
  const barTotal = bar.reduce((a, b) => a + b.n, 0);

  const rows: Row[] =
    phase === 'lumen'
      ? LUMEN.exceptions.map((e) => ({ tag: e.tag, verdict: e.verdict, account: e.account }))
      : phase === 'bright'
        ? [
            { tag: 'C1', verdict: f >= T.pass ? 'PASS' : 'REVIEW', account: BRIGHTFIELD.c1.account },
            { tag: 'C2', verdict: 'REVIEW', account: BRIGHTFIELD.c2.account },
          ]
        : [
            { tag: 'C1', verdict: 'PASS', account: COBALT.c1.account },
            { tag: 'C2', verdict: 'REVIEW', account: 'Travel & Entertainment' },
          ];
  const rowsAt = phase === 'lumen' ? T.toClaims + 8 : phase === 'bright' ? T.verifyB + 8 : T.verifyC + 4;
  const selQuote = phase === 'lumen' ? LUMEN.c1.quote : phase === 'bright' ? BRIGHTFIELD.c1.quote : COBALT.c1.quote;
  // Content of the list and detail leaves just before each switch.
  const swapOut = (at: number) => (f >= at - 12 && f < at + 12 ? 1 - progress(f, at - 10, 10) : 1);
  const listAlpha = phase === 'lumen' ? swapOut(T.toB) : phase === 'bright' ? swapOut(T.toC) : 1;
  const detailIn = progress(f, T.toClaims + 12, 12);
  const detailTop = splitY;
  const showClaims = f >= T.toClaims;

  const content = (
    <div style={{ position: 'absolute', inset: 0 }}>
      <BrowserFrame style={chromeIn(0)}>
        <Sidebar navIn={(i) => rise(f, T.chrome + 6 + i * 3, 12, 10)} brandIn={rise(f, T.chrome + 4, 12, 10)} learned={learned} learnedPop={learnedPop} />
        <TopBar close={closeName} style={rise(f, T.chrome + 8, 12, 8)} />
      </BrowserFrame>
      {/* Page head */}
      <div style={{ position: 'absolute', left: MAIN.x, top: HEAD.y, ...rise(f, T.chrome + 10, 12, 10) }}>
        <Swap a={titleA} b={titleB} t={titleT} style={css('sans', TYPE.ui, COLORS.ink)} />
        <div style={{ marginTop: 10 }}>
          <Swap a={metaA} b={metaB} t={titleT} style={css('sans', UI, COLORS.ash)} />
        </div>
      </div>
      <div style={{ position: 'absolute', left: 1190, top: HEAD.y - 6, ...rise(f, T.chrome + 12, 12, 10) }}>
        <div style={{ ...css('sans', UI, COLORS.ash), marginBottom: 8 }}>Extractor</div>
        <SelectBox w={474}>
          <Swap a={extA} b={extB} t={extT} style={css('sans', UI, COLORS.ink)} />
        </SelectBox>
      </div>
      <div style={{ position: 'absolute', left: 1680, top: HEAD.y + 36, ...rise(f, T.chrome + 14, 12, 10) }}>
        <Button label="Verify" accent w={136} press={Math.max(press(f, T.verify), press(f, T.verifyB), press(f, T.verifyC))} />
      </div>

      {/* Coverage */}
      {covOut > 0 && (
        <div style={{ position: 'absolute', left: 0, top: 0, opacity: covOut * progress(f, T.chrome + 14, 12), transform: `translateY(${-(1 - covOut) * 20}px)` }}>
          {covCols.map((c, i) => (
            <div key={c.label} style={{ position: 'absolute', left: MAIN.x + [0, 330, 600, 870, 1180][i], top: COVERAGE.y }}>
              <div style={{ display: 'flex', alignItems: 'center', gap: 10 }}>
                {c.dot && <span style={{ width: 14, height: 14, borderRadius: 7, backgroundColor: c.dot }} />}
                <span style={eyebrowStyle()}>{c.label}</span>
              </div>
              <div style={{ ...css('sans', TYPE.title, COLORS.ink), ...TABULAR, lineHeight: 1, marginTop: 12, opacity: f >= T.counts ? 1 : 0.25 }}>{c.value}</div>
              {c.sub && <div style={{ ...css('sans', UI, COLORS.ash), marginTop: 8, ...rise(f, T.countsEnd - 4, 10, 6) }}>{c.sub}</div>}
            </div>
          ))}
          <div style={{ position: 'absolute', left: MAIN.x, top: COVERAGE.bar, width: MAIN.right - MAIN.x, height: 8, borderRadius: 4, backgroundColor: COLORS.surface, overflow: 'hidden', display: 'flex' }}>
            {bar.map((b, i) => (
              <div key={i} style={{ height: 8, width: `${(b.n / barTotal) * 100 * progress(f, T.counts + i * 6, 24)}%`, backgroundColor: b.c, marginRight: 3 }} />
            ))}
          </div>
        </div>
      )}

      {/* Split: list card (full width until the switch to Claims) and detail card */}
      {(() => {
        const listW = mix(MAIN.right - MAIN.x, LIST.w, progress(f, T.toClaims, 16, 'standard'));
        return (
          <div
            style={{
              position: 'absolute',
              left: LIST.x,
              top: splitY,
              width: listW,
              height: SPLIT.bottom - splitY,
              borderRadius: RADII.card,
              backgroundColor: COLORS.paper,
              boxShadow: `0 0 0 1px ${COLORS.hairline}`,
              ...rise(f, T.chrome + 4, 14, 12),
            }}
          >
            <div style={{ position: 'absolute', left: 16, top: 14, display: 'flex', gap: 6 }}>
              {['Claims', 'Explanation'].map((t) => {
                const active = t === 'Explanation' ? 1 - progress(f, T.toClaims, 6) : progress(f, T.toClaims, 6);
                return (
                  <span key={t} style={{ ...css('sans', UI, COLORS.ink), padding: '6px 16px', borderRadius: RADII.control, backgroundColor: `rgba(243,242,238,${active})` }}>
                    {t}
                  </span>
                );
              })}
            </div>
            {showClaims && (
              <div style={{ position: 'absolute', right: 16, top: 14, display: 'flex', borderRadius: RADII.control, backgroundColor: COLORS.surface, padding: 4, ...rise(f, T.toClaims + 4, 10, 6) }}>
                {['Exceptions', 'All'].map((t) => {
                  const on = (t === 'All') === (phase === 'cobalt');
                  return (
                    <span key={t} style={{ ...css('sans', UI, on ? COLORS.ink : COLORS.ash), padding: '2px 14px', borderRadius: 6, backgroundColor: on ? COLORS.paper : 'transparent' }}>
                      {t}
                    </span>
                  );
                })}
              </div>
            )}
          </div>
        );
      })()}
      {f < T.toClaims + 12 && <ExplanationPane f={f} splitY={splitY} />}
      {showClaims && (
        <div style={{ position: 'absolute', left: 0, top: 0, opacity: listAlpha }}>
          <ClaimsList f={f} rows={rows} at={rowsAt} splitY={splitY} selectedQuote={selQuote} />
        </div>
      )}
      {showClaims && (
        <div
          style={{
            position: 'absolute',
            left: DETAIL.x,
            top: detailTop,
            width: DETAIL.w,
            height: SPLIT.bottom - detailTop,
            borderRadius: RADII.card,
            backgroundColor: COLORS.paper,
            boxShadow: `0 0 0 1px ${COLORS.hairline}`,
            opacity: detailIn,
            transform: `translateX(${(1 - enter(f, T.toClaims + 12, 14)) * 40}px)`,
          }}
        >
          <div style={{ position: 'absolute', left: PANE_PAD, top: 18, right: PANE_PAD, display: 'flex', alignItems: 'center', gap: 14, borderBottom: `1px solid ${COLORS.hairline}`, paddingBottom: 14 }}>
            <span style={css('mono', UI, COLORS.ash)}>C1</span>
            <Swap
              a={phase === 'cobalt' ? BRIGHTFIELD.c1.account : LUMEN.c1.account}
              b={phase === 'cobalt' ? COBALT.c1.account : BRIGHTFIELD.c1.account}
              t={phase === 'lumen' ? 0 : phase === 'bright' ? toB : toC}
              style={css('sans', UI, COLORS.ink)}
            />
            <span style={{ flex: 1 }} />
            <span style={css('sans', UI, COLORS.ash)}>{phase === 'lumen' ? '1 of 5' : '1 of 2'}</span>
          </div>
        </div>
      )}
      {showClaims && (
        <div style={{ position: 'absolute', left: 0, top: 0, opacity: listAlpha }}>
          {phase === 'lumen' && <LumenDetail f={f} top={detailTop} />}
          {phase === 'bright' && <BrightDetail f={f} top={detailTop} />}
          {phase === 'cobalt' && <CobaltDetail f={f} top={detailTop} />}
        </div>
      )}
    </div>
  );

  // The lesson leaves the Learned item and travels to the loop diagram (S4).
  const pillT = progress(f, T.out + 10, 34, 'standard');
  const pillFrom = { x: 120, y: 250 };
  const pill =
    f >= T.out + 10 ? (
      <div
        style={{
          position: 'absolute',
          left: mix(pillFrom.x, LESSON_PILL.x, pillT),
          top: mix(pillFrom.y, LESSON_PILL.y, pillT) - Math.sin(Math.PI * pillT) * 60,
          width: LESSON_PILL.w,
          boxSizing: 'border-box',
          padding: '8px 14px',
          borderRadius: RADII.control,
          backgroundColor: COLORS.chartreuse,
          opacity: enter(f, T.out + 10, 6),
        }}
      >
        <LessonText />
      </div>
    ) : null;

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bone }}>
      <div style={{ position: 'absolute', inset: 0, ...out }}>
        <div style={{ position: 'absolute', inset: 0, transform: `scale(${push(f)})`, transformOrigin: `${PUSH_O.x}px ${PUSH_O.y}px` }}>{content}</div>
      </div>
      {pill}
    </AbsoluteFill>
  );
};
