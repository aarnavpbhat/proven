// Thin outline icons (1.5 px at 20 px, scaled with size), drawn on with `t`. The sidebar glyphs (review shield,
// ledger table, learned book, benchmark bars) are the console's own (proven/web/index.html).
import { COLORS, STROKE } from '../brand/tokens';

interface IconProps {
  size?: number;
  color?: string;
  /** 0→1 stroke draw-on. */
  t?: number;
  strokeScale?: number;
}

const PATHS = {
  check: ['M4.5 10.5 8.5 14.5 15.5 6'],
  cross: ['M5.5 5.5 14.5 14.5', 'M14.5 5.5 5.5 14.5'],
  alert: ['M10 3.2a6.8 6.8 0 1 0 0.001 0', 'M10 6.5v4.2', 'M10 13.4v.2'],
  shield: ['M10 2.5 3.5 5v4.6c0 3.7 2.6 6.6 6.5 7.9 3.9-1.3 6.5-4.2 6.5-7.9V5L10 2.5Z', 'm7.3 10 2 2 3.5-3.8'],
  ledger: ['M5 3.5h10a2 2 0 0 1 2 2v9a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-9a2 2 0 0 1 2-2Z', 'M3 8h14', 'M8 8v8.5'],
  book: ['M10 5.5C8.3 4.3 6.2 3.8 3.5 3.8v11c2.7 0 4.8.5 6.5 1.7 1.7-1.2 3.8-1.7 6.5-1.7v-11c-2.7 0-4.8.5-6.5 1.7Z', 'M10 5.5v11'],
  bars: ['M3.5 16.5h13', 'M6 13.5v-4', 'M10 13.5v-9', 'M14 13.5v-6'],
  lock: ['M6 9V6.5a4 4 0 0 1 8 0V9', 'M5 9h10v8H5Z'],
  chip: ['M6 6h8v8H6Z', 'M8 3v3M12 3v3M8 14v3M12 14v3M3 8h3M3 12h3M14 8h3M14 12h3'],
  person: ['M10 3.5a3 3 0 1 0 .001 0', 'M4 17c.7-3.2 3-5 6-5s5.3 1.8 6 5'],
  laptop: ['M4.5 4.5h11v8h-11Z', 'M2.5 15.5h15'],
  arrowRight: ['M4 10h11', 'M11 6l4 4-4 4'],
  doc: ['M5.5 2.5h6l3.5 3.5v11.5h-9.5Z', 'M11.5 2.5V6H15', 'M8 10h5M8 13h5'],
  gate: ['M3.5 17V7.5L10 3l6.5 4.5V17', 'M7 17v-6h6v6', 'M3.5 17h13'],
  plug: ['M7 3v4M13 3v4', 'M5 7h10v3a5 5 0 0 1-10 0Z', 'M10 15v2.5'],
  loop: ['M15.5 7.5A6 6 0 0 0 4.6 7', 'M4 4v3.4h3.4', 'M4.5 12.5A6 6 0 0 0 15.4 13', 'M16 16v-3.4h-3.4'],
  layers: ['M10 3 2.5 7 10 11l7.5-4Z', 'M2.5 10.5 10 14.5l7.5-4', 'M2.5 14 10 18l7.5-4'],
  clock: ['M10 3.2a6.8 6.8 0 1 0 .001 0', 'M10 6.5V10l2.5 1.8'],
} as const;

export type IconName = keyof typeof PATHS;

export const Icon: React.FC<IconProps & { name: IconName }> = ({ name, size = 32, color = COLORS.ink, t = 1, strokeScale = 1 }) => {
  const tt = Math.max(0, Math.min(1, t));
  return (
    <svg width={size} height={size} viewBox="0 0 20 20" style={{ display: 'block', flex: 'none' }}>
      {PATHS[name].map((d, i) => (
        <path
          key={i}
          d={d}
          fill="none"
          stroke={color}
          strokeWidth={((STROKE.icon * 20) / Math.max(size, 20)) * 1.6 * strokeScale}
          strokeLinecap="round"
          strokeLinejoin="round"
          pathLength={1}
          strokeDasharray="1 1"
          strokeDashoffset={1 - tt}
          strokeOpacity={tt <= 0 ? 0 : 1}
        />
      ))}
    </svg>
  );
};
