// Chartreuse highlighter swipe: the "verified by Proven" mark. Draws on left to right with a slightly
// irregular top and bottom edge (seeded, so every frame and render is identical). Sits behind text.
import { random } from 'remotion';
import { COLORS } from '../brand/tokens';

const STEPS = 14;

/** Closed path for a w×h band whose long edges wobble by ±`rough` px. */
const bandPath = (w: number, h: number, rough: number, seed: string): string => {
  const top: string[] = [];
  const bottom: string[] = [];
  for (let i = 0; i <= STEPS; i++) {
    const x = (i / STEPS) * w;
    top.push(`${x.toFixed(1)},${((random(`${seed}-t${i}`) - 0.5) * 2 * rough).toFixed(1)}`);
    bottom.push(`${x.toFixed(1)},${(h + (random(`${seed}-b${i}`) - 0.5) * 2 * rough).toFixed(1)}`);
  }
  // Slightly rounded, angled ends like a real marker tip.
  return `M ${top.join(' L ')} L ${w + rough},${h * 0.5} L ${bottom.reverse().join(' L ')} L ${-rough},${h * 0.5} Z`;
};

export const Highlight: React.FC<{
  x: number;
  y: number;
  width: number;
  height: number;
  /** 0→1 draw-on progress, left to right. */
  t: number;
  seed?: string;
  color?: string;
  opacity?: number;
}> = ({ x, y, width, height, t, seed = 'hl', color = COLORS.chartreuse, opacity = 1 }) => {
  const rough = Math.max(1.5, height * 0.045);
  const pad = rough * 2;
  const shown = Math.max(0, Math.min(1, t)) * (width + pad * 2);
  if (shown <= 0) return null;
  const clipId = `hl-clip-${seed}`;
  return (
    <svg
      width={width + pad * 2}
      height={height + pad * 2}
      style={{ position: 'absolute', left: x - pad, top: y - pad, overflow: 'visible', opacity }}
    >
      <defs>
        <clipPath id={clipId}>
          <rect x={0} y={0} width={shown} height={height + pad * 2} />
        </clipPath>
      </defs>
      <path d={bandPath(width, height, rough, seed)} transform={`translate(${pad} ${pad})`} fill={color} clipPath={`url(#${clipId})`} />
    </svg>
  );
};
