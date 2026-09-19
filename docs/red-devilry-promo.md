# RED DEVILRY — Discord Recruitment Promo (WARDOGS / Bulkhead)

**Deliverable:** `assets/red-devilry-promo.mp4` — 44.2 s, 1080×1080 @ 30 fps, H.264 + AAC, loudness-normalized (−14 LUFS, true-peak −1 dB).
**Call to action:** `discord.gg/RedDevils`

## Concept
A 44-second recruitment trailer for the **Red Devilry** crew, built for the
**WARDOGS** (Bulkhead / Team17) early-access community. Beat-driven cuts synced
to a 7-line narration: cold-open signal → game stakes → logo reveal → crew creed
→ community humor (Mist the raccoon) → recruitment push → Discord end card.

## Beat sheet / narration
| # | Time (s) | Visual | Line |
|---|----------|--------|------|
| 1 | 0.0–2.5 | Bat-signal gag (`batsignalgif.gif`: eagle sigil lit over the city) + "THE SIGNAL IS LIT." | "The signal is lit." |
| 2 | 2.0–13.0 | WARDOGS "TIME TO SEED" key art (`seeding.png`), slow zoom-in; "WARDOGS // BULKHEAD" kicker + "100 PLAYERS. 3 TEAMS. ONE ZONE." | "A hundred dogs. Three teams. One zone. This is WARDOGS. All-out warfare on Bulkhead's frontier." |
| 3 | 12.6–16.5 | Red Devilry skull logo (`Red Devilry.png`) reveal with red flash + "RED DEVILRY" plate | "And this, is RED DEVILRY." |
| 4 | 16.0–21.8 | Golden eagle emblem (`Apollopng.png`), slow push + "DISCIPLINE. LOYALTY. TEETH." | "We fly disciplined. We fight loud. We hold the hill until the servers smoke." |
| 5 | 21.3–27.9 | Mist the raccoon (`mist.png`) close-up push-in + "MORALE OFFICER: MIST" / "YES, THAT'S A RACCOON. HE BITES." | "Morale officer? Yes. That's a raccoon. His name is Mist. He bites." |
| 6 | 27.4–35.6 | Key-art lateral pan + "RECRUITMENT OPEN" / "PILOTS - MEDICS - MANIACS. BRING YOUR RAGE." | "Recruitment is open. Pilots, medics, maniacs. Bring your rage. Leave your ego." |
| 7 | 35.1–44.2 | End card: logo + "JOIN THE WING" + `DISCORD.GG/REDDEVILS` pill + "WARDOGS EARLY ACCESS - TIME TO SEED" | "Join the wing. Discord dot GG, slash Red Devils. Red Devilry. Time to seed." |

Game facts in the copy (100 players, three teams, one control zone) come from
Bulkhead/Team17 WARDOGS coverage; "TIME TO SEED" is the key-art tagline.

## Source assets (from github.com/Goldenapollo7/Main)
Downloaded at production time into `assets/reddevils/` (git-ignored scratch;
originals live in the Main repo): `Red Devilry.png` (hero logo), `Red Devilry.jpg`,
`Apollopng.png` (eagle emblem), `seeding.png` (WARDOGS key art), `mist.png`
(Mist the raccoon), `batsignalgif.gif` (signal cold-open),
`Thank you for flying with Mist.gif` (reviewed but **excluded** — it carries a
burned-in profanity caption, so the raccoon still stands in for beat 5).

## Production pipeline (zero paid API keys)
- **Narration:** on-platform voice audition → one TTS clip per beat (`vidtools/work/vo/n1..n7.mp3`).
- **Typography:** Black Ops One + Rajdhani (OFL) rendered to alpha plates with
  ImageMagick (the ffmpeg static build lacks `drawtext`); auto-fit sizing per plate.
- **Motion/comp:** FFmpeg 7 static — `zoompan` push-ins/pans, `xfade` beat cuts
  (fadeblack / fadewhite), `overlay` plates, `noise` + `vignette` grade.
- **Music bed:** fully synthesized in FFmpeg (`aevalsrc` sub-bass drone + brown-noise
  air + 49 Hz pulse + braam hits on every cut), mixed under the narration,
  then `alimiter` + `loudnorm` (I=−14, TP=−1).
- **QC:** full-stream decode (1318/1318 frames), seek probes at every scene,
  `astats` peak check (−0.93 dBTP), frame grabs at all seven beats.

## Reproduce
```bash
pip install --user imageio-ffmpeg     # provides the static ffmpeg binary
ln -s "$(python3 -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')" vidtools/ffmpeg
cd vidtools && bash make_plates.sh && python3 build_promo.py
```
`build_promo.py` re-probes narration durations, re-derives scene timings,
renders the seven scenes, xfade-concats them and mixes the final audio to
`vidtools/work/red-devilry-promo.mp4` (~2 min of compute).
