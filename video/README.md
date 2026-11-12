# Proven — demo video (v4, the two-minute cut)

A 118-second demo for **Proven**, built with [Remotion](https://www.remotion.dev) (React + TypeScript): 1920×1080,
30 fps, 3,540 frames. Most of it (scenes 2–5, 70 s) is a walkthrough of the **real console**, captured with
Playwright (`npm run capture`) and presented with zooms, a cursor, rings and callouts; the rest is drawn in code. No
stock footage, no synthetic voice. The narration is recorded later and drops into fixed slots.

The previous 168-second cut (12 scenes, half of it on the fine-tuning research) is archived: render in
`out/archive/proven-demo-silent-168s-12-scenes-v3.mp4`, stills in `out/archive/stills-168s-cut/`, scene files in
`src/scenes/archive/` (excluded from the build).

The previous video is in `reference/previous-demo.mp4`; its editor project (now organised, see its
`ORGANIZATION.md`) is at `~/personal/projects/proven-demo-editor/`. This project copies and adapts its tokens,
motion helpers, components and check scripts.

| Read | For |
|---|---|
| `docs/storyboard.md` | scene-by-scene intent, frame ranges, carried elements, where every number and case comes from |
| `docs/script.md` | the narration, with per-line timecodes and slot lengths |
| `docs/recording-guide.md` | what the speakers record, how, and where the files go |
| `docs/critique-log.md` | what was checked in the stills of each cut, and what was fixed |
| `src/data/results.ts` | **every statistic on screen**, each with its source file; pending results |

## Setup

```sh
cd ~/proven/video
export PATH="$HOME/.nvm/versions/node/v24.19.0/bin:$PATH"   # Node 24 (the machine default is too old)
npm install
```

Fonts (Inter, IBM Plex Mono) load from Google Fonts at render time, so rendering needs internet access.

## Capture the console (only when the console or the walkthrough changes)

```sh
npm run capture     # starts a private copy of the console on :8766 (state in .scratch/, Sonnet proposals replayed
                    # from the cache, nothing sent), drives it, writes public/capture/*.png + src/data/capture.ts
```

It never touches the console on :8765 or the repo's `.proven/`. See `docs/storyboard.md`, "The captures", for what
the copy changes and what is added to the page (vendor names replaced by a grey tag). After a re-capture, check the
focus rects in `src/scenes/shared/capture-geom.ts` and the ring rects in the walkthrough scenes against the new
images (`.scratch/crop.sh shot x y w h` crops a CSS-px rect).

## Preview

```sh
npm run preview            # Remotion Studio at http://localhost:3000, composition "Demo"
```

In the Studio a pill at the top right shows which VO line is due and whether its take is recorded (it never appears
in a render). Subtitles show the script; turn them off with `SHOW_SUBTITLES` in `src/brand/tokens.ts`.

## Machine safety (read before rendering)

A model-training job may be running on this 24 GB Mac.

- Check free memory first: `sysctl -n kern.memorystatus_level` (a percentage). Below 25, wait. Never render below 20.
  The scripts in `scripts/` refuse to start below 25 by themselves.
- Iterate with single frames (`npm run frames`), not full renders. `remotion.config.ts` sets concurrency 1.
- A full render uses `--concurrency=2` at most.
- Scratch files go to `.scratch/` (git-ignored), never `/tmp`.

## Render

```sh
sysctl -n kern.memorystatus_level                     # ≥ 25
npm run render                                        # → out/proven-demo-2min.mp4 (concurrency 2)
# or explicitly:
npx remotion render src/index.ts Demo out/proven-demo-2min.mp4 --codec=h264 --concurrency=2
# without subtitles:
npx remotion render src/index.ts Demo out/proven-demo-nosubs.mp4 --codec=h264 --concurrency=2 --props='{"subtitles":false}'
# once voice takes are in public/: same command, name it e.g. out/proven-demo.mp4
```

Single frames and contact sheets for review:

```sh
npm run frames -- 120 900 2400 --scale 0.5           # → .scratch/frames/
npm run frames -- --sheet s3 --step 30               # one scene, tiled (needs ffmpeg)
npm run stills                                       # the key stills → out/stills/
```

## Drop in the voice

Follow `docs/recording-guide.md`. In short: `public/facecam/line-NN.mp4` (face cam, carries the voice) or
`public/voice/line-NN.wav` (voice only); set each take's `lead` (frames of room tone before the first word) in
`src/data/voice.ts`; `npm run check-data` confirms each take fits its slot. Nothing else is retimed.

## Update the numbers (pending results)

All statistics live in `src/data/results.ts`, each with its source; none is pending. To change one: set `value`,
point `source` at the file and table it came from, run `npm run check-data`, and look at the scene with
`npm run frames`. A future unknown result can be added with `pending(...)`: it renders as a dashed slot the size of a
value (`PendingValue`), so filling it in later changes no layout.

No narration line speaks a pending number; `docs/script.md` has an optional line if you want one.

## Checks

| Check | Command | Must be |
|---|---|---|
| Types (strict, no `any`) | `npm run typecheck` | clean |
| Purity (nothing animates outside the frame number) | `npm run purity` | clean |
| Data (timeline, sources, pending entries, script = timeline, takes fit their slots) | `npm run check-data` | clean |
| Text: overlap, cut, < 28 px, face-cam corner, under a subtitle | `npm run text-check` (every 5th frame) or `-- --scene s3 --every 1` | 0 issues |
| Static stretches > 36 frames (except the final hold) | `npm run dead-time` (or `-- --scene s6`) | none |
| Scene boundaries are continuous | `npm run cut-check` | all "continuous" |

The last three render frames: check memory first.

## Hard rules

- Every animated value is a pure function of `useCurrentFrame()`. No CSS transitions or animations, timers,
  `requestAnimationFrame`, `Math.random` (use `random(seed)`), `Date`. `npm run purity` enforces it.
- Easing only from `EASE` / `SPRING` in `src/brand/tokens.ts` via `src/lib/anim.ts`.
- Nothing under 28 px on screen. At most three type sizes per frame. Text inside the safe area; nothing important in
  the face-cam corner (`KEEP_CLEAR`, bottom left) or under a subtitle (`SUBTITLE_CLEAR`).
- No dead frames; every scene boundary is a carried element (see `docs/storyboard.md`).
- Near-monochrome, Inter, one chartreuse accent meaning *verified* (PASS, a confirmed lesson, "Gate: safe", the
  wordmark); red only for FAIL / flagged; amber only for REVIEW / advisory / pending.
- Never another company's name, logo or wordmark. The synthetic ledgers contain real vendor names (ad networks,
  cloud providers, airlines): rows show ID, memo and amount, never the vendor. Proven's own wordmark only.
- Every statistic from `src/data/results.ts`; never invent one. Case data (sentences, ledger rows, checker output)
  from `src/data/cases.ts`, regenerated by `scripts/py/*.py` against the repo, read-only.
- TypeScript strict, no `any`. Components `PascalCase.tsx`, utilities `kebab-case.ts`. No secrets.

## Layout

```
src/
  Root.tsx, Demo.tsx, index.ts    compositions; the nine scenes mounted from timeline.ts, voice slots on top
  timeline.ts                     FPS, BEAT, SCENES, VO (the narration), validateTimeline()
  brand/tokens.ts, fonts.ts       colours, type, layout, face cam, easing, spring
  lib/anim.ts, svg.ts, camera.ts  frame-driven motion helpers, text measurement (from the editor)
  data/results.ts                 every statistic, with sources and pending flags
  data/cases.ts                   the closes, sentences, ledger rows and checker output shown
  data/capture.ts                 GENERATED by npm run capture: the console screenshots and element boxes
  data/voice.ts                   take files and leads
  data/check.ts                   consistency checks run at load time
  components/                     CaptureView (captures under a camera, cursor, rings, callouts), ui, Icons,
                                  Highlight, Wordmark, Slots (FaceCam, VoiceTrack, Subtitles, VoPlaceholder), FontGate
  scenes/                         S1Hook, S2Paste, S3Waits, S4Gate, S5NextClose (the walkthrough), S6Loop, S7Proof,
                                  S8Next, S9Close; shared/ (geometry, incl. capture-geom.ts); archive/ (the 168 s cut)
  tools/                          TextAudit (for text-check), ContactSheet
scripts/                          checks, renders, capture-console.ts (lib.ts has the memory guard);
                                  py/ regenerates case data and runs the capture copy of the console
docs/                             storyboard, script, recording guide
public/                           capture/ (console screenshots), facecam/, voice/, audio/ (empty until recorded)
out/                              renders and stills (git-ignored)
reference/                        the previous video
```
