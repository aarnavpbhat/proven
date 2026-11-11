// Brand tokens. The only place to change the product name, colours, type, layout and motion curves.
// Adapted from the v2 editor project (~/personal/projects/proven-demo-editor/src/brand/tokens.ts). Plain data, no imports.

export const PRODUCT_NAME = 'Proven';

// Voice slots (src/components/Slots.tsx). Files that do not exist are skipped, so these can stay on.
export const SHOW_FACECAM = true;
// Subtitles show the script lines from src/timeline.ts (VO). On by default so a silent render reads on its own.
export const SHOW_SUBTITLES = true;

// Near-monochrome with one accent.
// chartreuse = verified (PASS, a confirmed lesson), flag = FAIL / flagged, partial = REVIEW / partial / pending.
// Nothing else uses them.
export const COLORS = {
  ink: '#0C0A08', // primary text, headlines
  obsidian: '#1A1919', // dark scenes
  ash: '#6E6A68', // secondary text on light
  hairline: '#E5E7EB', // card borders, dividers on light
  bone: '#F4F2F0', // light scene background
  paper: '#FFFFFF', // cards, product UI surfaces
  chartreuse: '#E4F222', // the only accent: verified
  flag: '#D93F2B', // FAIL, flagged
  partial: '#E8A23A', // REVIEW, partial, pending
  // Derived neutrals.
  obsidianRaised: '#252423', // cards on obsidian
  graphite: '#3A3837', // hairlines on obsidian
  mist: '#A6A3A0', // secondary text on obsidian
  stone: '#D6D3CF', // tertiary marks on light (inactive bars, ghost rows)
  surface: '#F3F2EE', // selected rows, table heads (console --surface-2)
  flagTint: '#FBE4E0', // FAIL chip / row tint
  partialTint: '#FCEFDB', // REVIEW chip / row tint
  flagInk: '#8C1D14', // FAIL text on its tint
  partialInk: '#7A5200', // REVIEW text on its tint
} as const;

export const FONTS = { sans: 'Inter', mono: 'IBM Plex Mono' } as const;

// px at 1920x1080. Nothing under 28. Max 3 sizes on screen at once.
export const TYPE = {
  wordmark: 208,
  display: 140,
  headline: 120,
  hero: 96, // hero sentences that must fit two lines
  lead: 72,
  title: 56,
  body: 44,
  ui: 36,
  label: 32,
  eyebrow: 28, // the minimum
} as const;

export const MIN_TEXT = 28;
export const LINE_HEIGHT = { display: 1.0, body: 1.3, ui: 1.35 } as const;
export const TRACKING = { display: -0.02, body: -0.005, eyebrow: 0.06 } as const; // em
export const WEIGHT = { regular: 400, medium: 500 } as const;

export const SPACE = { 1: 8, 2: 16, 3: 24, 4: 32, 6: 48, 8: 64, 12: 96, 16: 128 } as const;

export const CANVAS = { width: 1920, height: 1080 } as const;
export const SAFE = { x: 96, y: 54, width: 1728, height: 972 } as const;
export const COLUMN = { x: 160, width: 1600 } as const;

// Bottom-left picture-in-picture for the face cam. KEEP_CLEAR is the zone scenes leave empty of important content.
export const FACECAM = { x: 40, y: 770, width: 480, height: 270, radius: 20 } as const;
export const KEEP_CLEAR = { x: 0, y: 746, width: 544, height: 334 } as const;
// Subtitles: one line beside the face cam, bottom-aligned with it. Scene text stays out of SUBTITLE_CLEAR while one shows.
export const SUBTITLES = { x: 560, bottom: 1040, maxWidth: 1320, padX: 24, padY: 12, size: 32 } as const;
export const SUBTITLE_CLEAR = { x: 540, y: 953, width: 1380, height: 127 } as const;

export const RADII = { card: 16, ui: 12, control: 8, pill: 999 } as const;
export const STROKE = { border: 1, icon: 1.5, rule: 2, edge: 2 } as const;

// One standard curve, cubic-bezier(0.4, 0, 0.2, 1); enter/exit are its decelerate/accelerate halves. No overshoot.
export const EASE = {
  standard: [0.4, 0, 0.2, 1],
  enter: [0, 0, 0.2, 1],
  exit: [0.4, 0, 1, 1],
} as const;

// The one spring: tight UI hits (chips, checks, rows locking). Clamped, so it never overshoots.
export const SPRING = {
  ui: { damping: 200, stiffness: 320, mass: 0.6, overshootClamping: true },
} as const;

// Frames between items in a staggered group (rule: 2–4).
export const STAGGER = { tight: 2, base: 3, loose: 4 } as const;
