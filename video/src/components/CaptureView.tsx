// Real console captures (public/capture, made by scripts/capture-console.ts) under a frame-driven camera, with the
// video's own overlays on top: a cursor, rings, a spotlight and callouts. Everything here is a pure function of the
// frame number.
//
// Coordinates: focus rects, rings and cursor points are in the capture's CSS pixels (its viewport, CAPTURE_VIEW);
// the camera fits the current focus rect into STAGE (the frame minus the subtitle band) and every overlay is mapped
// through the same camera, so it stays on the UI element it marks while the camera moves.
import { Img, staticFile, useCurrentFrame } from 'remotion';
import { COLORS, RADII, TYPE } from '../brand/tokens';
import { CAPTURE_VIEW, SHOTS, type ShotId } from '../data/capture';
import { enter, mix, progress } from '../lib/anim';
import { css } from '../lib/svg';

export interface Rect {
  x: number;
  y: number;
  w: number;
  h: number;
}

/** The part of the frame the camera fits a focus into: clear of the subtitle band at the bottom. */
export const STAGE: Rect = { x: 96, y: 56, w: 1728, h: 860 };
/** The console's page colour (sampled from the captures), shown wherever the camera looks past a capture's edge. */
export const CONSOLE_CANVAS = '#FAFAF7';

export interface CamKey {
  /** Local frame the move to this key starts. */
  at: number;
  shot: ShotId;
  focus: Rect;
  /** Frames the camera takes to reach `focus` (default 20). */
  move?: number;
  /** Frames the crossfade takes when the shot changes (default 10). */
  fade?: number;
}

interface Pose {
  cx: number;
  cy: number;
  k: number;
}

const poseOf = (r: Rect): Pose => ({ cx: r.x + r.w / 2, cy: r.y + r.h / 2, k: Math.min(STAGE.w / r.w, STAGE.h / r.h) });

export interface Cam extends Pose {
  /** A capture rect (CSS px) in frame px. */
  toFrame: (r: Rect) => Rect;
  /** A capture point (CSS px) in frame px. */
  pt: (x: number, y: number) => { x: number; y: number };
}

/** While the camera holds on a focus it keeps pushing in slowly (a reading hold never freezes), capped. */
const DRIFT = { perFrame: 0.00035, maxFrames: 180 } as const;
const drift = (p: Pose, frames: number): Pose => ({ ...p, k: p.k * (1 + DRIFT.perFrame * Math.min(Math.max(0, frames), DRIFT.maxFrames)) });

export const camAt = (keys: CamKey[], f: number): Cam => {
  let p = poseOf(keys[0].focus);
  let settled = keys[0].at;
  for (let i = 1; i < keys.length; i++) {
    const start = keys[i].at;
    if (f < start) break;
    const move = keys[i].move ?? 20;
    // The hold before this move drifted; the move starts from there, so nothing jumps.
    p = drift(p, start - settled);
    const t = progress(f, start, move, 'standard');
    const q = poseOf(keys[i].focus);
    // Zoom interpolates in log space, so a push in and a pull out feel equally even.
    p = { cx: mix(p.cx, q.cx, t), cy: mix(p.cy, q.cy, t), k: Math.exp(mix(Math.log(p.k), Math.log(q.k), t)) };
    settled = start + move;
  }
  p = drift(p, f - settled);
  const ox = STAGE.x + STAGE.w / 2;
  const oy = STAGE.y + STAGE.h / 2;
  const pt = (x: number, y: number) => ({ x: ox + (x - p.cx) * p.k, y: oy + (y - p.cy) * p.k });
  return {
    ...p,
    pt,
    toFrame: (r: Rect) => {
      const a = pt(r.x, r.y);
      return { x: a.x, y: a.y, w: r.w * p.k, h: r.h * p.k };
    },
  };
};

/** The focus rect a camera pose shows (the inverse of poseOf), so a scene can start where the last one ended. */
export const focusAt = (keys: CamKey[], f: number): Rect => {
  const c = camAt(keys, f);
  const w = STAGE.w / c.k;
  const h = STAGE.h / c.k;
  return { x: c.cx - w / 2, y: c.cy - h / 2, w, h };
};

/** Shot layers visible at frame f: the last fully faded-in shot, then any still fading in, with their opacity. */
const layersAt = (keys: CamKey[], f: number): { shot: ShotId; opacity: number }[] => {
  const changes: { shot: ShotId; at: number; fade: number }[] = [];
  keys.forEach((k, i) => {
    if (i === 0 || k.shot !== keys[i - 1].shot) changes.push({ shot: k.shot, at: i === 0 ? -1e9 : k.at, fade: k.fade ?? 10 });
  });
  let base = 0;
  changes.forEach((c, i) => {
    if (progress(f, c.at, c.fade) >= 1) base = i;
  });
  return changes.slice(base).map((c, i) => ({ shot: c.shot, opacity: i === 0 ? 1 : progress(f, c.at, c.fade) })).filter((l) => l.opacity > 0);
};

export const CaptureView: React.FC<{ keys: CamKey[]; children?: (cam: Cam, f: number) => React.ReactNode; frame?: number }> = ({ keys, children, frame }) => {
  const current = useCurrentFrame();
  const f = frame ?? current;
  const cam = camAt(keys, f);
  const w = CAPTURE_VIEW.width * cam.k;
  const h = CAPTURE_VIEW.height * cam.k;
  const o = cam.pt(0, 0);
  return (
    <div style={{ position: 'absolute', inset: 0, overflow: 'hidden', backgroundColor: CONSOLE_CANVAS }}>
      {layersAt(keys, f).map((l) => (
        <Img
          key={l.shot}
          src={staticFile(SHOTS[l.shot].file)}
          style={{ position: 'absolute', left: o.x, top: o.y, width: w, height: h, opacity: l.opacity, maxWidth: 'none' }}
        />
      ))}
      {children?.(cam, f)}
    </div>
  );
};

// ── Overlays (frame space) ─────────────────────────────────────────────────────────────────────────────────────

export type Tone = 'ink' | 'pass' | 'fail' | 'review';
const TONE: Record<Tone, string> = { ink: COLORS.ink, pass: '#B8C400', fail: COLORS.flag, review: COLORS.partial };
const TONE_BAR: Record<Tone, string> = { ink: COLORS.ink, pass: COLORS.chartreuse, fail: COLORS.flag, review: COLORS.partial };

/** Darkens everything outside `r` (frame px) by `t`, so the marked element reads first. */
export const Spotlight: React.FC<{ r: Rect; t: number; pad?: number }> = ({ r, t, pad = 10 }) => {
  if (t <= 0) return null;
  const x = r.x - pad;
  const y = r.y - pad;
  const w = r.w + pad * 2;
  const h = r.h + pad * 2;
  const rr = 14;
  const hole = `M ${x + rr} ${y} H ${x + w - rr} Q ${x + w} ${y} ${x + w} ${y + rr} V ${y + h - rr} Q ${x + w} ${y + h} ${x + w - rr} ${y + h} H ${x + rr} Q ${x} ${y + h} ${x} ${y + h - rr} V ${y + rr} Q ${x} ${y} ${x + rr} ${y} Z`;
  return (
    <svg width={1920} height={1080} style={{ position: 'absolute', left: 0, top: 0 }}>
      <path d={`M -10 -10 H 1930 V 1090 H -10 Z ${hole}`} fillRule="evenodd" fill={COLORS.ink} opacity={0.32 * t} />
    </svg>
  );
};

/** A rounded ring around `r` (frame px), drawn on with `t`. */
export const Ring: React.FC<{ r: Rect; t: number; tone?: Tone; pad?: number }> = ({ r, t, tone = 'ink', pad = 10 }) => {
  if (t <= 0) return null;
  const w = r.w + pad * 2;
  const h = r.h + pad * 2;
  return (
    <svg width={w + 8} height={h + 8} style={{ position: 'absolute', left: r.x - pad - 4, top: r.y - pad - 4, overflow: 'visible' }}>
      <rect x={4} y={4} width={w} height={h} rx={14} fill="none" stroke={TONE[tone]} strokeWidth={5} pathLength={1} strokeDasharray="1 1" strokeDashoffset={1 - Math.min(1, t)} />
    </svg>
  );
};

/** A label in the video's own type (not the console's): paper card, coloured bar on the left for its meaning. */
export const Callout: React.FC<{ x: number; y: number; text: string; f: number; at: number; until?: number; tone?: Tone; size?: number; maxWidth?: number }> = ({
  x,
  y,
  text,
  f,
  at,
  until = 1e9,
  tone = 'ink',
  size = TYPE.ui,
  maxWidth = 1100,
}) => {
  const t = enter(f, at, 12) * (1 - progress(f, until, 8, 'exit'));
  if (t <= 0) return null;
  return (
    <div
      style={{
        position: 'absolute',
        left: x,
        top: y,
        maxWidth,
        padding: '14px 24px 14px 22px',
        borderRadius: RADII.ui,
        backgroundColor: COLORS.paper,
        boxShadow: `0 0 0 1px ${COLORS.hairline}, 0 12px 32px rgba(12,10,8,0.16)`,
        borderLeft: `8px solid ${TONE_BAR[tone]}`,
        opacity: t,
        transform: `translateY(${(1 - t) * 14}px)`,
      }}
    >
      <div style={{ ...css('sans', size, COLORS.ink, 500), whiteSpace: 'normal', lineHeight: 1.25 }}>{text}</div>
    </div>
  );
};

export interface CursorPoint {
  /** Local frame the cursor arrives here. */
  at: number;
  /** Capture CSS px. */
  x: number;
  y: number;
  click?: boolean;
}

/** The pointer, gliding between capture points (mapped through the camera each frame), with a ripple on a click. */
export const Cursor: React.FC<{ cam: Cam; f: number; path: CursorPoint[]; from?: number; until?: number }> = ({ cam, f, path, from, until }) => {
  const start = from ?? path[0].at - 12;
  const end = until ?? path[path.length - 1].at + 30;
  const vis = progress(f, start, 8) * (1 - progress(f, end, 8));
  if (vis <= 0) return null;
  let x = path[0].x;
  let y = path[0].y;
  for (let i = 1; i < path.length; i++) {
    const a = path[i - 1];
    const b = path[i];
    const t = progress(f, a.at + 4, Math.max(1, b.at - a.at - 4), 'standard');
    if (t > 0) {
      x = mix(a.x, b.x, t);
      y = mix(a.y, b.y, t);
    }
  }
  const p = cam.pt(x, y);
  const clicks = path.filter((q) => q.click);
  const press = clicks.some((q) => f >= q.at && f < q.at + 5);
  return (
    <>
      {clicks.map((q) => {
        const t = progress(f, q.at, 16, 'enter');
        if (t <= 0 || t >= 1) return null;
        const c = cam.pt(q.x, q.y);
        return <div key={q.at} style={{ position: 'absolute', left: c.x - 40 * t - 10, top: c.y - 40 * t - 10, width: 20 + 80 * t, height: 20 + 80 * t, borderRadius: '50%', border: `4px solid ${COLORS.ink}`, opacity: (1 - t) * vis, boxSizing: 'border-box' }} />;
      })}
      <svg width={48} height={60} viewBox="0 0 24 30" style={{ position: 'absolute', left: p.x - 4, top: p.y - 2, opacity: vis, transform: `scale(${press ? 0.88 : 1})`, transformOrigin: '4px 2px' }}>
        <path d="M2 1 L2 23 L7.5 17.5 L11.5 27 L15 25.5 L11 16.5 L19 16.5 Z" fill={COLORS.ink} stroke={COLORS.paper} strokeWidth={1.6} strokeLinejoin="round" />
      </svg>
    </>
  );
};

/** A key-press chip (e.g. "⌘ V"), shown from `at` for `dur` frames. */
export const Keycap: React.FC<{ x: number; y: number; text: string; f: number; at: number; dur?: number }> = ({ x, y, text, f, at, dur = 36 }) => {
  const t = enter(f, at, 8) * (1 - progress(f, at + dur, 8, 'exit'));
  if (t <= 0) return null;
  return (
    <div style={{ position: 'absolute', left: x, top: y, padding: '10px 22px', borderRadius: RADII.ui, backgroundColor: COLORS.obsidian, opacity: t, transform: `translateY(${(1 - t) * 10}px)` }}>
      <span style={{ ...css('mono', TYPE.title, COLORS.paper, 500) }}>{text}</span>
    </div>
  );
};

/** Spotlight + ring around a capture rect for [at, until), in one call. */
export const Mark: React.FC<{ cam: Cam; f: number; r: Rect; at: number; until: number; tone?: Tone; dim?: boolean; pad?: number }> = ({ cam, f, r, at, until, tone = 'ink', dim = true, pad }) => {
  const t = progress(f, at, 14) * (1 - progress(f, until, 8));
  if (t <= 0) return null;
  const fr = cam.toFrame(r);
  return (
    <>
      {dim && <Spotlight r={fr} t={t} pad={(pad ?? 10) + 4} />}
      <Ring r={fr} t={progress(f, at, 16) * (1 - progress(f, until, 8))} tone={tone} pad={pad} />
    </>
  );
};
