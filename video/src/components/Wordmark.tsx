// "Proven" in Inter 400 with a chartreuse highlighter swipe behind its lower half, drawn left to right.
// Deliberately plain: title case, no symbol, no slant, nothing that echoes another company's mark.
import { COLORS, PRODUCT_NAME, TYPE } from '../brand/tokens';
import { css, measure } from '../lib/svg';
import { Highlight } from './Highlight';

export const wordmarkWidth = (size: number = TYPE.wordmark): number => measure(PRODUCT_NAME, 'sans', size);

export const Wordmark: React.FC<{
  x: number;
  /** Top of the text box. */
  y: number;
  size?: number;
  /** Highlighter draw-on, 0→1. */
  swipe: number;
  color?: string;
  opacity?: number;
}> = ({ x, y, size = TYPE.wordmark, swipe, color = COLORS.ink, opacity = 1 }) => {
  const w = wordmarkWidth(size);
  return (
    <div style={{ position: 'absolute', left: x, top: y, width: w, height: size, opacity }}>
      {/* Band covers x-height to just below the baseline, overhanging the letters a little on each side. */}
      <Highlight x={-size * 0.06} y={size * 0.42} width={w + size * 0.12} height={size * 0.46} t={swipe} seed="wordmark" />
      <div style={{ ...css('sans', size, color), position: 'absolute', left: 0, top: 0, lineHeight: 1 }}>{PRODUCT_NAME}</div>
    </div>
  );
};
