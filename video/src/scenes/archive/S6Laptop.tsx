// Scene 6 · Laptop fine-tune (2010–2280), VO 9. The laptop's base line is S5's teaching curve, flattened; the laptop
// draws on from it and its screen fills with the run's settings; the right column gives the trainable share as a
// sliver of a bar that a lens opens up. The screen then grows to fill the frame and becomes S8.
// Principles: staging (laptop left, numbers right), line work before fills (the laptop strokes draw first),
// anticipation (the lens forms before the sliver is named), follow-through (labels trail their values by 4 frames),
// secondary action (slow push), arcs (the lens callout swings out on an arc).
import { AbsoluteFill, interpolateColors, useCurrentFrame } from 'remotion';
import { COLORS, STROKE, TYPE } from '../brand/tokens';
import { StatText } from '../components/ui';
import { RESULTS, known } from '../data/results';
import { drawOn, lift, mix, progress, rise } from '../lib/anim';
import { css } from '../lib/svg';
import { LAPTOP_BASE, S7_TITLE, SCREEN } from './shared/s7-geom';

const LEN = 270;
const F = RESULTS.finetune;
const T = { suffix: 6, laptop: 4, lines: 50, params: 56, bar: 100, lens: 150, pct: 170, gb: 112, out: 242 } as const;

const LINES = [
  `lora   rank ${known(F.loraRank)} · last ${known(F.loraLayers)} layers`,
  `data   ${known(F.rebuiltRows)} rows · ${known(F.worldsTrainWorlds)} worlds`,
  'target rebuilt by a blind teacher',
  `iters  ${known(F.rebuiltIters)} from the base model`,
  'lock   one GPU job at a time',
];

const BARX = { x: 980, y: 452, w: 780, h: 26 } as const;

export const S6Laptop: React.FC = () => {
  const f = useCurrentFrame();
  const push = mix(1, 1.025, progress(f, 0, LEN, 'standard'));
  const out = lift(f, T.out, 8, 16);
  const grow = progress(f, T.out + 8, 19, 'standard');
  const sliver = (BARX.w * (F.trainablePct.value ?? 0)) / 100;
  const lensT = progress(f, T.lens, 18, 'standard');
  const lensC = { x: BARX.x + sliver / 2, y: BARX.y + BARX.h / 2 };

  // The screen: laptop pose → full frame, paper → obsidian.
  const scr = {
    x: mix(960 + (SCREEN.x - 960) * push, -2, grow),
    y: mix(900 + (SCREEN.y - 900) * push, -2, grow),
    w: mix(SCREEN.w * push, 1924, grow),
    h: mix(SCREEN.h * push, 1084, grow),
  };
  const screenFill = interpolateColors(grow, [0, 1], [COLORS.paper, COLORS.obsidian]);
  const screenIn = progress(f, T.laptop + 10, 14);

  return (
    <AbsoluteFill style={{ backgroundColor: COLORS.bone }}>
      <div style={{ position: 'absolute', inset: 0, transform: `scale(${push})`, transformOrigin: '960px 900px' }}>
          {/* Laptop line work (the screen panel itself is drawn outside `out` so it can grow into S8) */}
          <svg width={1920} height={1080} style={{ position: 'absolute', left: 0, top: 0, opacity: 1 - progress(f, T.out + 8, 10) }}>
            <rect x={SCREEN.x - 14} y={SCREEN.y - 14} width={SCREEN.w + 28} height={SCREEN.h + 28} rx={SCREEN.r + 8} fill="none" stroke={COLORS.ink} strokeWidth={3} {...drawOn(progress(f, T.laptop + 6, 26, 'standard'))} />
            <path d={`M ${LAPTOP_BASE.x0} ${LAPTOP_BASE.y} H ${LAPTOP_BASE.x1}`} fill="none" stroke={COLORS.ink} strokeWidth={3} strokeLinecap="round" />
            <path d={`M ${LAPTOP_BASE.x1} ${LAPTOP_BASE.y} L ${SCREEN.x + SCREEN.w + 40} ${SCREEN.y + SCREEN.h + 64} H ${SCREEN.x - 40} L ${LAPTOP_BASE.x0} ${LAPTOP_BASE.y}`} fill="none" stroke={COLORS.ink} strokeWidth={3} strokeLinejoin="round" {...drawOn(progress(f, T.laptop, 18, 'standard'))} />
          </svg>
        <div style={{ position: 'absolute', inset: 0, ...out }}>
          <div style={{ position: 'absolute', left: S7_TITLE.x, top: S7_TITLE.y, display: 'flex', alignItems: 'baseline' }}>
            <span style={{ ...css('sans', S7_TITLE.size, COLORS.ink), lineHeight: 1.2, ...rise(f, 2, 12, 10) }}>Qwen2.5-3B</span>
            <span style={{ ...css('sans', S7_TITLE.size, COLORS.ash), lineHeight: 1.2, ...rise(f, T.suffix, 12, 10) }}>-Instruct, 4-bit, open weights</span>
          </div>
          <div style={{ position: 'absolute', left: BARX.x, top: 700, ...rise(f, T.gb, 12, 10) }}>
            <span style={{ ...css('sans', TYPE.body, COLORS.ink), lineHeight: 1 }}>{known(F.memoryGb)}</span>
            <span style={{ ...css('sans', TYPE.eyebrow, COLORS.ash), marginLeft: 16 }}>of memory, on one laptop</span>
          </div>

          {/* Right column */}
          <div style={{ position: 'absolute', left: BARX.x, top: 250, ...rise(f, T.params, 12, 12) }}>
            <StatText stat={F.trainableM} size={TYPE.lead} slot={260} />
            <div style={{ ...css('sans', TYPE.eyebrow, COLORS.ash), marginTop: 14 }}>trainable parameters (LoRA adapters)</div>
          </div>
          <div style={{ position: 'absolute', left: BARX.x, top: BARX.y - 48, ...css('sans', TYPE.eyebrow, COLORS.ash), ...rise(f, T.bar, 10, 8) }}>the whole model</div>
          <div style={{ position: 'absolute', left: BARX.x, top: BARX.y, width: BARX.w * progress(f, T.bar, 24, 'standard'), height: BARX.h, borderRadius: 6, backgroundColor: COLORS.stone }} />
          <div style={{ position: 'absolute', left: BARX.x, top: BARX.y, width: Math.max(2, sliver), height: BARX.h, backgroundColor: COLORS.ink, opacity: progress(f, T.bar + 20, 6) }} />
          {/* Lens: a circle on the sliver and a callout arcing out below it */}
          <svg width={1920} height={1080} style={{ position: 'absolute', left: 0, top: 0 }}>
            <circle cx={lensC.x} cy={lensC.y} r={30} fill="none" stroke={COLORS.ink} strokeWidth={STROKE.rule} {...drawOn(lensT)} />
            <path d={`M ${lensC.x + 21} ${lensC.y + 21} Q ${lensC.x + 60} ${lensC.y + 110} ${lensC.x + 120} ${lensC.y + 118}`} fill="none" stroke={COLORS.ink} strokeWidth={STROKE.rule} strokeLinecap="round" {...drawOn(progress(f, T.lens + 10, 14, 'standard'))} />
          </svg>
          <div style={{ position: 'absolute', left: lensC.x + 136, top: lensC.y + 84, ...rise(f, T.pct, 12, 10) }}>
            <StatText stat={F.trainablePct} size={TYPE.lead} slot={240} />
            <div style={{ ...css('sans', TYPE.eyebrow, COLORS.ash), marginTop: 12 }}>of the weights are trained</div>
          </div>
        </div>
      </div>
      {/* The screen, which becomes S8's frame */}
      <div
        style={{
          position: 'absolute',
          left: scr.x,
          top: scr.y,
          width: scr.w,
          height: scr.h,
          borderRadius: mix(SCREEN.r, 0, grow),
          backgroundColor: screenFill,
          boxShadow: `0 0 0 1px ${COLORS.hairline}`,
          opacity: screenIn,
          overflow: 'hidden',
        }}
      >
        <div style={{ position: 'absolute', left: 36, top: 34, opacity: 1 - progress(f, T.out, 8) }}>
          {LINES.map((l, i) => (
            <div key={l} style={{ ...css('mono', TYPE.eyebrow, COLORS.ink), lineHeight: '48px', ...rise(f, T.lines + i * 9, 8, 6) }}>
              {l}
            </div>
          ))}
          {f >= T.lines + LINES.length * 9 && f < T.out && Math.floor(f / 8) % 2 === 0 && <div style={{ width: 16, height: 30, backgroundColor: COLORS.ink, marginTop: 8 }} />}
        </div>
      </div>
    </AbsoluteFill>
  );
};
