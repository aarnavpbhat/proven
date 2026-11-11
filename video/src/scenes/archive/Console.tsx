// The review console, rebuilt as components from proven/web/index.html + style.css, at a scale where nothing is
// under 28 px. Same structure and words as the real page: sidebar (Review, Ledger, Learned, Benchmark), the Close
// menu in the top bar, "Network off (enforced) · v0.1.0", Extractor + Verify, Coverage, Claims | Explanation, and a
// claim-detail pane. Everything animated is passed in as values; nothing here reads the frame.
import { COLORS, PRODUCT_NAME, RADII } from '../brand/tokens';
import { FRAME, MAIN, SIDEBAR, TOPBAR } from '../scenes/shared/console-geom';
import { css } from '../lib/svg';
import { eyebrowStyle } from './ui';
import { Icon, type IconName } from './Icons';

export const UI = 28; // smallest UI text
export const UI_L = 32; // list and field text
export const UI_XL = 36;

export const BrowserFrame: React.FC<{ children: React.ReactNode; style?: React.CSSProperties }> = ({ children, style }) => (
  <div
    style={{
      position: 'absolute',
      left: FRAME.x,
      top: FRAME.y,
      width: FRAME.w,
      height: FRAME.h,
      borderRadius: RADII.card,
      backgroundColor: COLORS.paper,
      boxShadow: `0 0 0 1px ${COLORS.hairline}, 0 24px 48px -32px rgba(12,10,8,0.18)`,
      overflow: 'hidden',
      ...style,
    }}
  >
    <div style={{ position: 'absolute', left: 0, right: 0, top: 0, height: FRAME.bar, borderBottom: `1px solid ${COLORS.hairline}`, display: 'flex', alignItems: 'center', padding: '0 22px' }}>
      <div style={{ display: 'flex', gap: 10 }}>
        {[0, 1, 2].map((i) => (
          <div key={i} style={{ width: 13, height: 13, borderRadius: 7, backgroundColor: COLORS.hairline }} />
        ))}
      </div>
      <div style={{ margin: '0 auto', height: 38, padding: '0 22px', borderRadius: RADII.control, backgroundColor: COLORS.bone, display: 'flex', alignItems: 'center', ...css('sans', UI, COLORS.ash) }}>127.0.0.1:8765</div>
      <div style={{ width: 60 }} />
    </div>
    <div style={{ position: 'absolute', left: 0, top: FRAME.bar, right: 0, bottom: 0 }}>{children}</div>
  </div>
);

/** Coordinates inside the frame body from absolute ones. */
export const fx = (x: number): number => x - FRAME.x;
export const fy = (y: number): number => y - FRAME.y - FRAME.bar;

const NAV: { label: string; icon: IconName }[] = [
  { label: 'Review', icon: 'shield' },
  { label: 'Ledger', icon: 'ledger' },
  { label: 'Learned', icon: 'book' },
  { label: 'Benchmark', icon: 'bars' },
];

export const Sidebar: React.FC<{ navIn: (i: number) => React.CSSProperties; learned: number; learnedPop: number; brandIn: React.CSSProperties }> = ({ navIn, learned, learnedPop, brandIn }) => (
  <div style={{ position: 'absolute', left: 0, top: 0, width: SIDEBAR.w, bottom: 0, borderRight: `1px solid ${COLORS.hairline}` }}>
    <div style={{ position: 'absolute', left: 30, top: 26, display: 'flex', alignItems: 'center', gap: 14, ...brandIn }}>
      <div style={{ width: 26, height: 26, borderRadius: 7, backgroundColor: COLORS.chartreuse, boxShadow: `inset 0 0 0 2px ${COLORS.ink}` }} />
      <span style={css('sans', UI_XL, COLORS.ink)}>{PRODUCT_NAME}</span>
    </div>
    {NAV.map((n, i) => (
      <div
        key={n.label}
        style={{
          position: 'absolute',
          left: 14,
          width: SIDEBAR.w - 28,
          top: 110 + i * 64,
          height: 54,
          borderRadius: RADII.control,
          backgroundColor: i === 0 ? COLORS.surface : 'transparent',
          display: 'flex',
          alignItems: 'center',
          gap: 16,
          paddingLeft: 18,
          boxSizing: 'border-box',
          ...navIn(i),
        }}
      >
        <Icon name={n.icon} size={30} color={COLORS.ink} />
        <span style={css('sans', UI_L, COLORS.ink)}>{n.label}</span>
        {n.label === 'Learned' && learned > 0 && (
          <span
            style={{
              ...css('sans', UI, COLORS.ink, 500),
              marginLeft: 'auto',
              marginRight: 14,
              minWidth: 36,
              height: 36,
              borderRadius: 18,
              backgroundColor: COLORS.chartreuse,
              display: 'flex',
              alignItems: 'center',
              justifyContent: 'center',
              opacity: learnedPop,
              transform: `translateY(${(1 - learnedPop) * 6}px)`,
            }}
          >
            {learned}
          </span>
        )}
      </div>
    ))}
  </div>
);

/** Text that swaps between two values with a short vertical crossfade (`t` 0 → 1). */
export const Swap: React.FC<{ a: string; b: string; t: number; style: React.CSSProperties }> = ({ a, b, t, style }) => (
  <span style={{ position: 'relative', display: 'inline-block', whiteSpace: 'nowrap' }}>
    <span style={{ ...style, display: 'inline-block', opacity: 1 - Math.min(1, t * 2), transform: `translateY(${-t * 10}px)` }}>{a}</span>
    <span style={{ ...style, position: 'absolute', left: 0, top: 0, opacity: Math.max(0, t * 2 - 1), transform: `translateY(${(1 - t) * 10}px)` }}>{b}</span>
  </span>
);

export const TopBar: React.FC<{ close: React.ReactNode; style?: React.CSSProperties }> = ({ close, style }) => (
  <div style={{ position: 'absolute', left: SIDEBAR.w, right: 0, top: 0, height: TOPBAR.h, borderBottom: `1px solid ${COLORS.hairline}`, ...style }}>
    <div style={{ position: 'absolute', left: fx(MAIN.x) - SIDEBAR.w, top: 0, height: TOPBAR.h, display: 'flex', alignItems: 'center', gap: 14 }}>
      {close}
      <span style={css('sans', 30, COLORS.ash)}>⌄</span>
      <span style={css('sans', 30, COLORS.ash)}>›</span>
      <span style={css('sans', UI, COLORS.ink)}>Review</span>
    </div>
    <div style={{ position: 'absolute', right: 44, top: 0, height: TOPBAR.h, display: 'flex', alignItems: 'center', ...css('sans', UI, COLORS.ash) }}>
      Network <span style={{ color: COLORS.ink, margin: '0 8px' }}>off</span> (enforced) · v0.1.0
    </div>
  </div>
);

export const SelectBox: React.FC<{ children: React.ReactNode; w: number }> = ({ children, w }) => (
  <div
    style={{
      width: w,
      height: 56,
      boxSizing: 'border-box',
      borderRadius: RADII.control,
      boxShadow: `inset 0 0 0 1px ${COLORS.hairline}`,
      display: 'flex',
      alignItems: 'center',
      padding: '0 20px',
      gap: 12,
      backgroundColor: COLORS.paper,
    }}
  >
    <span style={{ flex: 1, display: 'flex' }}>{children}</span>
    <span style={css('sans', 30, COLORS.ash)}>⌄</span>
  </div>
);

export const Button: React.FC<{ label: string; accent?: boolean; press?: number; w?: number; h?: number; size?: number }> = ({ label, accent, press = 0, w, h = 56, size = UI_L }) => (
  <div
    style={{
      height: h,
      width: w,
      padding: w ? undefined : '0 24px',
      boxSizing: 'border-box',
      borderRadius: RADII.control,
      backgroundColor: accent ? COLORS.ink : COLORS.paper,
      boxShadow: accent ? undefined : `inset 0 0 0 1px ${COLORS.hairline}`,
      display: 'flex',
      alignItems: 'center',
      justifyContent: 'center',
      transform: `scale(${1 - 0.05 * Math.sin(Math.PI * press)})`,
      flex: 'none',
    }}
  >
    <span style={css('sans', size, accent ? COLORS.paper : COLORS.ink)}>{label}</span>
  </div>
);

/** A term chip in the "Searched" row: written (plain), model (dashed: a guess), learned (chartreuse: confirmed). */
export const TermChip: React.FC<{ text: string; kind: 'written' | 'model' | 'learned'; style?: React.CSSProperties }> = ({ text, kind, style }) => (
  <span
    style={{
      ...css('sans', UI, COLORS.ink),
      display: 'inline-flex',
      alignItems: 'center',
      height: 40,
      padding: '0 12px',
      borderRadius: RADII.control,
      boxSizing: 'border-box',
      backgroundColor: kind === 'learned' ? COLORS.chartreuse : kind === 'written' ? COLORS.surface : 'transparent',
      border: kind === 'model' ? `1.5px dashed ${COLORS.ash}` : '1.5px solid transparent',
      ...style,
    }}
  >
    {text}
  </span>
);

export { eyebrowStyle, css };
