// Voice slots on top of the scenes, so recorded takes drop in without retiming anything (adapted from the v2 editor).
//  FaceCam      public/facecam/line-NN.mp4 picture-in-picture (FACECAM, bottom left), carrying the voice. Scenes
//               keep that corner clear (KEEP_CLEAR). Lines less than a second apart stay up; otherwise it pops.
//  VoiceTrack   public/voice/line-NN.wav for lines with no face-cam file; public/audio/music.wav ducked under it.
//  Subtitles    the script line (src/timeline.ts VO) on an obsidian pill beside the face cam, phrase by phrase.
//               Toggle with SHOW_SUBTITLES (tokens) or the `subtitles` input prop. The last line has none: the end
//               card says it.
//  VoPlaceholder  Studio preview only (never in a render): which line is due and whether its take exists.
// Every overlay uses layout="none" so no full-frame wrapper blinds the text audit's occlusion test.
import { Audio, OffthreadVideo, Sequence, getInputProps, getRemotionEnvironment, getStaticFiles, interpolate, staticFile, useCurrentFrame } from 'remotion';
import { COLORS, FACECAM, RADII, SHOW_FACECAM, SHOW_SUBTITLES, SUBTITLES, TYPE } from '../brand/tokens';
import { MUSIC_FILE, TAKES, facecamFile, pad2, voiceFile } from '../data/voice';
import { enter, exit, mix, progress } from '../lib/anim';
import { css, measure } from '../lib/svg';
import { END_CARD_SCENE, TOTAL_FRAMES, VO, type VoLine } from '../timeline';
import { eyebrowStyle } from './ui';

const has = (name: string): boolean => getStaticFiles().some((f) => f.name === name);
const leadOf = (line: number): number => TAKES.find((t) => t.line === line)?.lead ?? 0;
const POP = 8;
const STAY = 30; // lines closer than this keep the face cam up

const FaceClip: React.FC<{ line: VoLine; popIn: boolean; popOut: boolean; duration: number }> = ({ line, popIn, popOut, duration }) => {
  const frame = useCurrentFrame();
  const t = (popIn ? enter(frame, 0, POP) : 1) * (popOut ? 1 - exit(frame, duration - POP, POP) : 1);
  return (
    <div
      style={{
        position: 'absolute',
        left: FACECAM.x,
        top: FACECAM.y,
        width: FACECAM.width,
        height: FACECAM.height,
        borderRadius: FACECAM.radius,
        overflow: 'hidden',
        backgroundColor: COLORS.obsidian,
        boxShadow: `0 0 0 1px ${COLORS.graphite}`,
        opacity: t,
        transform: `scale(${mix(0.86, 1, t)})`,
        transformOrigin: '0% 100%',
      }}
    >
      <OffthreadVideo src={staticFile(facecamFile(line.n))} style={{ width: '100%', height: '100%', objectFit: 'cover' }} />
    </div>
  );
};

export const FaceCam: React.FC = () => {
  if (!SHOW_FACECAM) return null;
  const lines = VO.filter((l) => has(facecamFile(l.n)));
  return (
    <>
      {lines.map((l, i) => {
        const from = l.from - leadOf(l.n);
        const next = lines[i + 1];
        const prev = lines[i - 1];
        const end = next && next.from - leadOf(next.n) - l.to < STAY ? next.from - leadOf(next.n) : l.to;
        const popIn = !prev || from - prev.to >= STAY;
        const popOut = end === l.to;
        return (
          <Sequence key={l.n} from={from} durationInFrames={end - from} layout="none" name={`face cam · line ${l.n}`}>
            <FaceClip line={l} popIn={popIn} popOut={popOut} duration={end - from} />
          </Sequence>
        );
      })}
    </>
  );
};

export const VoiceTrack: React.FC = () => {
  const audioOnly = VO.filter((l) => !has(facecamFile(l.n)) && has(voiceFile(l.n)));
  const clamp = { extrapolateLeft: 'clamp', extrapolateRight: 'clamp' } as const;
  const spoken = VO.filter((l) => has(facecamFile(l.n)) || has(voiceFile(l.n)));
  const music = (f: number): number => {
    const fade = interpolate(f, [0, 15, TOTAL_FRAMES - 30, TOTAL_FRAMES], [0, 1, 1, 0], clamp);
    const duck = spoken.length ? Math.max(...spoken.map((l) => interpolate(f, [l.from - 12, l.from - 2, l.to - 6, l.to + 14], [0, 1, 1, 0], clamp))) : 0;
    return fade * mix(0.4, 0.18, duck);
  };
  return (
    <>
      {audioOnly.map((l) => (
        <Sequence key={l.n} from={l.from - leadOf(l.n)} durationInFrames={l.to - l.from + leadOf(l.n)} layout="none" name={`voice · line ${l.n}`}>
          <Audio src={staticFile(voiceFile(l.n))} />
        </Sequence>
      ))}
      {has(MUSIC_FILE) && <Audio src={staticFile(MUSIC_FILE)} volume={music} />}
    </>
  );
};

// ── Subtitles ─────────────────────────────────────────────────────────────────────────────────────────────────
export interface Cue {
  text: string;
  from: number;
  to: number;
}

/** A line's phrases (split at " | "), spread over its slot in proportion to their length. */
export const cuesFor = (l: VoLine): Cue[] => {
  // Phrases longer than one comfortable line are split at the space nearest their middle.
  const MAX = 66;
  const split = (p: string): string[] => {
    if (p.length <= MAX) return [p];
    const mid = Math.floor(p.length / 2);
    let at = -1;
    for (let d = 0; d < mid; d++) {
      if (p[mid + d] === ' ') { at = mid + d; break; }
      if (p[mid - d] === ' ') { at = mid - d; break; }
    }
    return at < 0 ? [p] : [...split(p.slice(0, at)), ...split(p.slice(at + 1))];
  };
  const parts = l.text.split(' | ').map((p) => p.trim()).flatMap(split);
  const end = l.to - 6;
  const total = parts.reduce((a, p) => a + p.length, 0);
  let at = l.from;
  return parts.map((text, i) => {
    const len = i === parts.length - 1 ? end - at : Math.round(((end - l.from) * text.length) / total);
    const cue = { text, from: at, to: at + len };
    at += len;
    return cue;
  });
};

const CUE_FADE = 4;
const PAD_X = SUBTITLES.padX;
const PAD_Y = SUBTITLES.padY;
const SIZE = SUBTITLES.size;

const LineSubtitles: React.FC<{ cues: Cue[] }> = ({ cues }) => {
  const frame = useCurrentFrame() + cues[0].from;
  const first = cues[0].from;
  const last = cues[cues.length - 1].to;
  const pill = progress(frame, first, CUE_FADE) * (1 - progress(frame, last - CUE_FADE, CUE_FADE));
  const widthOf = (text: string): number => Math.min(SUBTITLES.maxWidth, measure(text, 'sans', SIZE) + PAD_X * 2);
  const i = Math.max(0, cues.findIndex((c) => frame >= c.from && frame < c.to));
  const cue = cues[i];
  // The pill grows at once (the new words never sit outside it) and eases only when it shrinks.
  const prevW = i === 0 ? widthOf(cue.text) : widthOf(cues[i - 1].text);
  const width = widthOf(cue.text) >= prevW ? widthOf(cue.text) : mix(prevW, widthOf(cue.text), progress(frame, cue.from, CUE_FADE + 2));
  const textIn = 1; // phrases swap at once: a fading phrase would leave an empty pill for a few frames
  return (
    <div
      data-subtitle
      style={{
        position: 'absolute',
        left: SUBTITLES.x,
        top: SUBTITLES.bottom - SIZE * 1.35 - PAD_Y * 2,
        width,
        boxSizing: 'border-box',
        padding: `${PAD_Y}px ${PAD_X}px`,
        borderRadius: RADII.ui,
        backgroundColor: COLORS.obsidian,
        boxShadow: `0 0 0 1px ${COLORS.graphite}`,
        opacity: pill,
      }}
    >
      <div style={{ ...css('sans', SIZE, COLORS.paper), lineHeight: 1.35, whiteSpace: 'nowrap', opacity: textIn }}>{cue.text}</div>
    </div>
  );
};

export const subtitlesOn = (): boolean => {
  const p = getInputProps() as { subtitles?: boolean };
  return typeof p.subtitles === 'boolean' ? p.subtitles : SHOW_SUBTITLES;
};

export const Subtitles: React.FC = () => {
  if (!subtitlesOn()) return null;
  return (
    <>
      {VO.filter((l) => l.scene !== END_CARD_SCENE).map((l) => {
        const cues = cuesFor(l);
        return (
          <Sequence key={l.n} from={cues[0].from} durationInFrames={cues[cues.length - 1].to - cues[0].from} layout="none" name={`subtitles · line ${l.n}`}>
            <LineSubtitles cues={cues} />
          </Sequence>
        );
      })}
    </>
  );
};

// ── Studio-only VO indicator ──────────────────────────────────────────────────────────────────────────────────
export const VoPlaceholder: React.FC = () => {
  const frame = useCurrentFrame();
  const env = getRemotionEnvironment();
  if (!env.isStudio || env.isRendering) return null;
  const line = VO.find((l) => frame >= l.from - leadOf(l.n) && frame < l.to);
  if (!line) return null;
  const recorded = has(facecamFile(line.n)) || has(voiceFile(line.n));
  const label = `VO ${pad2(line.n)} · speaker ${TAKES.find((t) => t.line === line.n)?.speaker ?? 1} · ${recorded ? 'recorded' : 'placeholder'}${line.pending ? ' · has pending words' : ''}`;
  return (
    <div
      data-audit-ignore
      style={{
        position: 'absolute',
        right: 24,
        top: 20,
        padding: '6px 14px',
        borderRadius: RADII.pill,
        backgroundColor: recorded ? COLORS.obsidian : COLORS.partial,
        ...eyebrowStyle(recorded ? COLORS.paper : COLORS.ink),
        fontSize: TYPE.eyebrow,
      }}
    >
      {label}
    </div>
  );
};
