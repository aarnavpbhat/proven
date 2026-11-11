# Recording guide

The video is finished without a voice. Every line has a fixed slot; a recorded take drops into its slot and nothing
else moves. This page says what to record, how, and where the files go.

## 1. What to record

Fifteen takes, one per line of `docs/script.md`, read exactly as written (the subtitles show the script text, so a
changed word must be changed in the script and in `src/timeline.ts` too). Suggested speakers:

| Speaker | Lines |
|---|---|
| 1 | 1, 11, 12, 13, 14, 15 (hook, loop, proof, the pre-registered test, next, close) |
| 2 | 2, 3, 4, 5, 6, 7 (walkthrough: paste, verify, the FAIL, the model proposing, the waiting claim) |
| 3 | 8, 9, 10 (walkthrough: the safety gate, confirming once, the next close) |

Lines 2–10 run over real screen captures of the console; read them as someone showing the screen, not announcing.
"Campaign" in line 7 is the model's word on screen: a slight stress on it helps.

Each take must fit its slot. The slot length is in `docs/script.md` next to each line (e.g. line 10: 11.0 s). Read a
little under it: a take that runs long is flagged by `npm run check-data`. The script never needs more than 2.5 words
per second; at a calm pace every line fits with room to spare.

Do not record line 15 with a face cam if you want the end card clean: the end card has no subtitle and the face cam
would sit over a static hold. Audio-only is fine for it.

Line 13 is a number people will quote: read "none of four hundred twenty-nine" plainly, without emphasis that
sounds like a guarantee.

## 2. Two ways to record

**A. Face cam (video + voice), like the previous video.** Landscape 16:9, head and shoulders, plain background, no
clothing logos or brand marks in frame. Any resolution ≥ 960×540; it is shown at 480×270, bottom left, with rounded
corners. The audio track of the clip *is* the voice.

**B. Voice only.** A WAV (48 kHz, 24-bit or 16-bit, mono). Use this when you don't want a face on screen.

You can mix the two per line. During the walkthrough (lines 2–10) a face cam sits over the bottom-left corner of the
console captures; the camera keeps everything that matters out of that corner, so either choice works there.

## 3. How to record each take

1. Quiet room, the same mic and distance for every take.
2. Start recording, wait about half a second (room tone), read the line once, wait half a second, stop.
3. Do two or three takes per line; keep the best.
4. Level: peaks around −6 dBFS, no clipping. If you can, normalise every take to −16 LUFS (e.g.
   `ffmpeg -i in.wav -af loudnorm=I=-16:TP=-1.5:LRA=11 out.wav`).

## 4. Where the files go

| Take | Put it at |
|---|---|
| Face cam for line N | `public/facecam/line-NN.mp4` (H.264 + AAC, e.g. `line-04.mp4`) |
| Voice only for line N | `public/voice/line-NN.wav` |
| Optional music bed | `public/audio/music.wav` (ducked under the voice automatically) |

`NN` is two digits (`01` … `15`). A missing file is simply skipped. If both exist for a line, the face-cam clip wins.

Trim each file so it starts with the half-second of room tone and ends shortly after the last word.

## 5. Line the takes up (one number per line)

Each line's first word should land on its frame in `docs/script.md` ("first word at"). The file is placed so that it
starts `lead` frames *before* that frame. Set `lead` for each line in `src/data/voice.ts` (`TAKES`): it is the time
from the start of the file to the first word, in frames (30 per second). The default is 15 (half a second).

To measure it: open the file in any editor (or run
`ffmpeg -i public/voice/line-04.wav -af silencedetect=n=-40dB:d=0.2 -f null -` and read the first
`silence_end`), multiply the seconds by 30, and round.

Nothing else needs retiming. Scenes are built to the slots, not to the takes.

## 6. Check and preview

```sh
export PATH="$HOME/.nvm/versions/node/v24.19.0/bin:$PATH"
npm run check-data      # lists each take found, its length and its slot; fails if one runs over
npm run preview         # Remotion Studio; a pill at the top right says, per line, "recorded" or "placeholder"
```

The pill only appears in the Studio preview, never in a render. Subtitles stay on by default; turn them off with
`SHOW_SUBTITLES = false` in `src/brand/tokens.ts`, or for one render with `--props='{"subtitles":false}'`.

## 7. Render with the voice

See `README.md`, "Render". The output then has sound; name it e.g. `out/proven-demo.mp4`.
