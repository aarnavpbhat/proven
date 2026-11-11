// Small UI primitives shared by every scene: eyebrows, verdict chips, cards, and the pending-result placeholder.
import { COLORS, RADII, TYPE } from '../brand/tokens';
import type { Verdict } from '../data/cases';
import { fmt, type Stat } from '../data/results';
import { TABULAR, css } from '../lib/svg';
import { Icon } from './Icons';

export const eyebrowStyle = (color: string = COLORS.ash): React.CSSProperties => ({
  ...css('sans', TYPE.eyebrow, color, 500),
  letterSpacing: '0.06em',
  textTransform: 'uppercase',
});

export const Eyebrow: React.FC<{ children: React.ReactNode; color?: string; style?: React.CSSProperties }> = ({ children, color, style }) => (
  <div style={{ ...eyebrowStyle(color), ...style }}>{children}</div>
);

const VERDICT_LOOK: Record<Verdict, { bg: string; fg: string; icon: 'check' | 'cross' | 'alert' }> = {
  PASS: { bg: COLORS.chartreuse, fg: COLORS.ink, icon: 'check' },
  FAIL: { bg: COLORS.flagTint, fg: COLORS.flagInk, icon: 'cross' },
  REVIEW: { bg: COLORS.partialTint, fg: COLORS.partialInk, icon: 'alert' },
};

export const verdictColor = (v: Verdict): string => (v === 'PASS' ? COLORS.chartreuse : v === 'FAIL' ? COLORS.flag : COLORS.partial);

/** The console's verdict tag: icon + word, always written out (never colour alone). */
export const VerdictChip: React.FC<{ verdict: Verdict; size?: number; t?: number; style?: React.CSSProperties; dark?: boolean }> = ({
  verdict,
  size = TYPE.eyebrow,
  t = 1,
  style,
}) => {
  const look = VERDICT_LOOK[verdict];
  return (
    <div
      style={{
        display: 'inline-flex',
        alignItems: 'center',
        gap: size * 0.3,
        height: size * 1.6,
        padding: `0 ${size * 0.5}px 0 ${size * 0.36}px`,
        borderRadius: RADII.control,
        backgroundColor: look.bg,
        flex: 'none',
        ...style,
      }}
    >
      <Icon name={look.icon} size={size * 0.95} color={look.fg} t={t} strokeScale={1.3} />
      <span style={{ ...css('sans', size, look.fg, 500), letterSpacing: '0.05em' }}>{verdict}</span>
    </div>
  );
};

/** White hairline card, absolutely positioned. */
export const Card: React.FC<{
  x: number;
  y: number;
  w: number;
  h: number;
  radius?: number;
  dark?: boolean;
  children?: React.ReactNode;
  style?: React.CSSProperties;
  clip?: boolean;
}> = ({ x, y, w, h, radius = RADII.card, dark, children, style, clip = true }) => (
  <div
    style={{
      position: 'absolute',
      left: x,
      top: y,
      width: w,
      height: h,
      borderRadius: radius,
      backgroundColor: dark ? COLORS.obsidianRaised : COLORS.paper,
      boxShadow: `0 0 0 1px ${dark ? COLORS.graphite : COLORS.hairline}`,
      overflow: clip ? 'hidden' : 'visible',
      ...style,
    }}
  >
    {children}
  </div>
);

/**
 * A result that is not known yet. Same box as the value it stands in for (pass the width the value would take), a
 * dashed outline and the words "pending" — so filling in src/data/results.ts later changes no layout.
 */
export const PendingValue: React.FC<{ width: number; height: number; dark?: boolean; label?: string; size?: number; dash?: number }> = ({
  width,
  height,
  dark,
  label = 'pending',
  size = TYPE.eyebrow,
  dash = 0,
}) => (
  <div style={{ position: 'relative', width, height, display: 'flex', alignItems: 'center', justifyContent: 'center', flex: 'none' }}>
    {/* `dash` is a frame-driven offset: pass e.g. -frame * 0.6 for slowly marching dashes. */}
    <svg width={width} height={height} style={{ position: 'absolute', left: 0, top: 0 }}>
      <rect x={1} y={1} width={width - 2} height={height - 2} rx={RADII.control} fill="none" stroke={dark ? COLORS.mist : COLORS.ash} strokeWidth={2} strokeDasharray="8 7" strokeDashoffset={dash} />
    </svg>
    <span style={{ ...eyebrowStyle(dark ? COLORS.mist : COLORS.ash), fontSize: size, position: 'relative' }}>{label}</span>
  </div>
);

/** A statistic from results.ts at a given size, or its pending placeholder in the same box. */
export const StatText: React.FC<{
  stat: Stat;
  size: number;
  color?: string;
  dark?: boolean;
  /** Width the placeholder takes (the value's expected width). */
  slot: number;
  unit?: boolean;
  style?: React.CSSProperties;
}> = ({ stat, size, color = COLORS.ink, dark, slot, unit, style }) => {
  const text = fmt(stat, { unit });
  if (text === null)
    return (
      <div style={{ height: size, display: 'flex', alignItems: 'center', ...style }}>
        <PendingValue width={slot} height={Math.max(TYPE.eyebrow * 1.7, size * 0.9)} dark={dark} />
      </div>
    );
  return <span style={{ ...css('sans', size, color), ...TABULAR, lineHeight: 1, ...style }}>{text}</span>;
};
