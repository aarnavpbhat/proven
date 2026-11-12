// Text audit (not part of the video). Mounted after the content when the render gets inputProps { audit: true }.
// After every frame commits, it measures every visible line of DOM text and logs one JSON line that
// scripts/text-check.ts collects. It flags:
//   overlap   two different texts whose boxes intersect, or a text drawn under another text
//   cut       a text box partly outside the frame, or partly outside a clipping container (overflow: hidden)
//   hidden    a text box partly covered by something solid (a word cut by an occluding card)
//   small     on-screen size under MIN_TEXT
//   facecam   text inside the face-cam corner (KEEP_CLEAR)
//   subtitle  scene text inside the subtitle band (SUBTITLE_CLEAR) while a subtitle is on screen
// 3D text drawn by WebGL (Label3D) is not DOM and is not audited.
import { useLayoutEffect } from 'react';
import { useCurrentFrame } from 'remotion';
import { CANVAS, KEEP_CLEAR, MIN_TEXT, SUBTITLE_CLEAR } from '../brand/tokens';

export interface TextIssue {
  kind: 'overlap' | 'cut' | 'hidden' | 'small' | 'facecam' | 'subtitle';
  text: string;
  other?: string;
  detail: string;
}

interface Line {
  id: number;
  text: string;
  r: DOMRect;
  el: Element;
}

const snippet = (s: string) => (s.length > 40 ? `${s.slice(0, 37)}...` : s);

const visibleChain = (el: Element | null): boolean => {
  let opacity = 1;
  for (let e = el; e && e instanceof HTMLElement; e = e.parentElement) {
    const cs = getComputedStyle(e);
    if (cs.display === 'none' || cs.visibility === 'hidden') return false;
    opacity *= Number(cs.opacity);
  }
  return opacity > 0.05;
};

type Cover = { kind: 'shown' } | { kind: 'opaque' } | { kind: 'text'; text: string };

const opaque = (e: Element): boolean => {
  if (['IMG', 'VIDEO', 'CANVAS'].includes(e.tagName)) return true;
  const m = getComputedStyle(e).backgroundColor.match(/rgba?\(([^)]+)\)/);
  if (!m) return false;
  const parts = m[1].split(',').map((v) => parseFloat(v));
  return (parts.length < 4 ? 1 : parts[3]) >= 0.9;
};

/**
 * What is on top of `el` at (x, y)? `shown` if el itself (or the same text); `opaque` if a solid card, photo or canvas
 * covers it on purpose; `text` if another text sits over it with see-through gaps between its glyphs, which is an
 * overlap even when every sample point is covered. Only the cover's own chain up to the shared ancestor counts, so a
 * scene background behind both never makes a text cover look solid.
 */
const coverAt = (el: Element, x: number, y: number): Cover | null => {
  if (x < 0 || y < 0 || x >= CANVAS.width || y >= CANVAS.height) return null;
  const top = document.elementFromPoint(x, y);
  if (!top || top === el || el.contains(top) || top.contains(el)) return { kind: 'shown' };
  // elementFromPoint ignores opacity: a faded-out element on top hides nothing.
  if (!visibleChain(top)) return { kind: 'shown' };
  for (let e: Element | null = top; e && !e.contains(el); e = e.parentElement) {
    if (opaque(e)) return { kind: 'opaque' };
  }
  // Another text covers this point only if one of the top element's own text nodes is drawn here; a transparent
  // wrapper that merely contains text elsewhere does not count.
  for (const n of Array.from(top.childNodes)) {
    if (n.nodeType !== Node.TEXT_NODE || !(n.textContent ?? '').trim()) continue;
    const range = document.createRange();
    range.selectNodeContents(n);
    if (Array.from(range.getClientRects()).some((r) => x >= r.left && x <= r.right && y >= r.top && y <= r.bottom)) {
      return { kind: 'text', text: (n.textContent ?? '').trim() };
    }
  }
  return { kind: 'shown' };
};

/** Boxes of every ancestor that clips its content (overflow other than visible). */
const clipBoxes = (el: Element): DOMRect[] => {
  const out: DOMRect[] = [];
  for (let e = el.parentElement; e && e !== document.body; e = e.parentElement) {
    const cs = getComputedStyle(e);
    if (cs.overflowX !== 'visible' || cs.overflowY !== 'visible') out.push(e.getBoundingClientRect());
  }
  return out;
};

export const auditText = (): TextIssue[] => {
  const issues: TextIssue[] = [];
  const lines: Line[] = [];
  // While any subtitle is visible, scene text in its band would sit under it.
  const subtitleOn = Array.from(document.querySelectorAll('[data-subtitle]')).some((e) => visibleChain(e));
  const walker = document.createTreeWalker(document.body, NodeFilter.SHOW_TEXT);
  let id = 0;
  for (let n = walker.nextNode(); n; n = walker.nextNode()) {
    const text = (n.textContent ?? '').trim();
    const el = n.parentElement;
    if (!text || !el || el.closest('[data-audit-ignore]') || !visibleChain(el)) continue;
    const range = document.createRange();
    range.selectNodeContents(n);
    const scale = el instanceof HTMLElement && el.offsetWidth > 0 ? el.getBoundingClientRect().width / el.offsetWidth : 1;
    const fontPx = parseFloat(getComputedStyle(el).fontSize) * scale;
    const nodeId = id++;
    for (const r of Array.from(range.getClientRects())) {
      if (r.width < 1 || r.height < 1) continue;
      const inside = r.right > 0 && r.bottom > 0 && r.left < CANVAS.width && r.top < CANVAS.height;
      if (!inside) continue;
      if (r.left < 0 || r.top < 0 || r.right > CANVAS.width || r.bottom > CANVAS.height) {
        issues.push({
          kind: 'cut',
          text: snippet(text),
          detail: `box ${Math.round(r.left)},${Math.round(r.top)}–${Math.round(r.right)},${Math.round(r.bottom)}`,
        });
      }
      for (const c of clipBoxes(el)) {
        if (r.left < c.left - 1 || r.top < c.top - 1 || r.right > c.right + 1 || r.bottom > c.bottom + 1) {
          issues.push({
            kind: 'cut',
            text: snippet(text),
            detail: `clipped by its container (text ${Math.round(r.top)}–${Math.round(r.bottom)}, container ${Math.round(c.top)}–${Math.round(c.bottom)})`,
          });
          break;
        }
      }
      // Sample along the middle of the line: all under a solid card = occluded on purpose (skip); some = cut word;
      // under another text = overlap.
      const ys = r.top + r.height / 2;
      const samples = [r.left + 3, r.left + r.width / 2, r.right - 3].map((x) => coverAt(el, x, ys)).filter((v): v is Cover => v !== null);
      const solid = samples.filter((c) => c.kind === 'opaque').length;
      if (samples.length > 0 && solid === samples.length) continue;
      if (solid > 0)
        issues.push({
          kind: 'hidden',
          text: snippet(text),
          detail: `${solid}/${samples.length} sample points covered`,
        });
      const over = samples.find((c): c is Extract<Cover, { kind: 'text' }> => c.kind === 'text');
      if (over)
        issues.push({
          kind: 'overlap',
          text: snippet(text),
          other: snippet(over.text),
          detail: 'drawn under another text',
        });
      if (fontPx < MIN_TEXT - 0.5)
        issues.push({
          kind: 'small',
          text: snippet(text),
          detail: `${fontPx.toFixed(1)} px on screen, box ${Math.round(r.left)},${Math.round(r.top)}–${Math.round(r.right)},${Math.round(r.bottom)}`,
        });
      const k = KEEP_CLEAR;
      if (r.right > k.x && r.left < k.x + k.width && r.bottom > k.y && r.top < k.y + k.height) {
        issues.push({
          kind: 'facecam',
          text: snippet(text),
          detail: `box ${Math.round(r.left)},${Math.round(r.top)}–${Math.round(r.right)},${Math.round(r.bottom)}`,
        });
      }
      const sb = SUBTITLE_CLEAR;
      if (subtitleOn && !el.closest('[data-subtitle]') && r.right > sb.x && r.left < sb.x + sb.width && r.bottom > sb.y && r.top < sb.y + sb.height) {
        issues.push({
          kind: 'subtitle',
          text: snippet(text),
          detail: `box ${Math.round(r.left)},${Math.round(r.top)}–${Math.round(r.right)},${Math.round(r.bottom)}`,
        });
      }
      lines.push({ id: nodeId, text, r, el });
    }
  }
  for (let i = 0; i < lines.length; i++) {
    for (let j = i + 1; j < lines.length; j++) {
      const a = lines[i];
      const b = lines[j];
      if (a.id === b.id) continue;
      // Compare glyph bands, not content boxes: a content box includes accent space above the caps, so lines
      // set at line-height 1.0 would always "touch". The band from 20% to 80% of the box holds caps and x-height.
      const band = (r: DOMRect) => ({
        top: r.top + r.height * 0.2,
        bottom: r.bottom - r.height * 0.2,
      });
      const w = Math.min(a.r.right, b.r.right) - Math.max(a.r.left, b.r.left);
      const h = Math.min(band(a.r).bottom, band(b.r).bottom) - Math.max(band(a.r).top, band(b.r).top);
      if (w <= 3 || h <= 3) continue;
      const area = w * h;
      const minArea = Math.min(a.r.width * a.r.height, b.r.width * b.r.height);
      if (area > 0.12 * minArea)
        issues.push({
          kind: 'overlap',
          text: snippet(a.text),
          other: snippet(b.text),
          detail: `${Math.round(w)}×${Math.round(h)} px`,
        });
    }
  }
  return issues;
};

export const TextAudit: React.FC = () => {
  const frame = useCurrentFrame();
  useLayoutEffect(() => {
    console.log(`TEXT_AUDIT ${JSON.stringify({ frame, issues: auditText() })}`);
  });
  return null;
};
