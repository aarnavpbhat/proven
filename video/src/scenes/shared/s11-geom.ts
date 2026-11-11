// The closing wordmark (S11), and its highlighter band, which S10's road line becomes.
import { TYPE } from '../../brand/tokens';
import { wordmarkWidth } from '../../components/Wordmark';

export const WM = { x: 160, y: 466, size: TYPE.wordmark } as const;
/** The band the Wordmark component draws (see Wordmark.tsx: x −6%, y 42%, width +12%, height 46% of the size). */
export const band = () => ({ x: WM.x - WM.size * 0.06, y: WM.y + WM.size * 0.42, w: wordmarkWidth(WM.size) + WM.size * 0.12, h: WM.size * 0.46 });
/** How much of the band S10 has drawn when S11 starts. */
export const BAND_START = 0.3;
