# RED DEVILRY — Discord Recruitment Promo (WARDOGS / Bulkhead)

**Deliverable:** `assets/red-devilry-promo.mp4` — 39.5 s, 1080×1080 @ 30 fps, H.264 + AAC, loudness-normalized (−14 LUFS).
**Call to action:** `discord.gg/RedDevils`

## Concept
A 40-second recruitment trailer for the **Red Devilry** crew, built for the
**WARDOGS** (Bulkhead / Team17) early-access community. Beat-driven cuts:
cold-open signal → game stakes → logo reveal → crew creed → community humor
(Mist the raccoon) → recruitment push → Discord end card.

## Beat sheet / narration
| # | Time (s) | Visual | Line |
|---|----------|--------|------|
| 1 | 0.0–2.8 | Bat-signal gag (eagle sigil over the city) | "The signal is lit." |
| 2 | 2.3–10.5 | WARDOGS "TIME TO SEED" key art, slow zoom | "A hundred dogs. Three teams. One zone. This is Wardogs: all-out warfare on Bulkhead's frontier." |
| 3 | 10.0–13.9 | Red Devilry skull logo reveal + white flash | "And this, is Red Devilry." |
| 4 | 13.4–19.4 | Golden eagle emblem, slow push | "We fly disciplined. We fight loud. We hold the hill until the servers smoke." |
| 5 | 18.9–24.6 | Mist the raccoon close-up | "Morale officer? Yes. That's a raccoon. His name is Mist. He bites." |
| 5b | 24.1–26.1 | "Thank you for flying with Mist" heli gag (profanity band cropped + encoder artifact patched) | (music sting) "AIR SUPPORT: ALSO MIST." |
| 6 | 25.6–32.4 | Key art lateral pan | "Recruitment is open. Pilots, medics, maniacs. Bring your rage. Leave your ego." |
| 7 | 31.9–39.5 | End card: logo + JOIN THE WING + discord.gg/RedDevils | "Join the wing. Discord dot GG, slash Red Devils. Red Devilry. Time to seed." |

## Source assets (from github.com/Goldenapollo7/Main)
Downloaded at production time into `assets/reddevils/` (git-ignored scratch):
`Red Devilry.png` (hero logo), `Red Devilry.jpg`, `Apollopng.png` (eagle emblem),
`seeding.png` (WARDOGS key art), `mist.png` (Mist the raccoon),
`batsignalgif.gif` (signal cold-open), `Thank you for flying with Mist.gif` (air-support gag).

## Production pipeline (zero paid API keys)
- **Narration:** on-platform TTS voice audition → 7 beat clips, one per scene.
- **Typography:** Black Ops One + Rajdhani (OFL) rendered to alpha plates with
  ImageMagick (this ffmpeg static build lacks `drawtext`).
- **Motion/comp:** FFmpeg 7 static — `zoompan` push-ins/pans, `xfade` beat cuts
  (fadeblack/fadewhite), `overlay` plates, `noise`+`vignette` grade.
- **Music bed:** fully synthesized in FFmpeg (`aevalsrc` sub-bass drone + brown-noise
  air + 49 Hz pulse + braam hits on every cut), mixed under narration, `loudnorm`.
- **QC:** ffprobe stream/duration checks, per-beat RMS checks, frame grabs at every
  scene + transition. Two source defects fixed in prep: the flying-Mist GIF ships a
  profanity band ("…FUCKERS ;)") which is cropped out, and a white encoder-artifact
  column which is clone-patched per frame (124/160 frames).

## Reproduce
Builder scripts (plates, scenes, assembly) live outside the repo scratch space;
the pipeline is plain FFmpeg + ImageMagick and re-runs from `assets/reddevils/`
plus `work/vo/beat*.mp3` narration in ~2 min of compute.
