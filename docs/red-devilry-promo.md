# RED DEVILRY — Discord Recruitment Promo (WARDOGS / Bulkhead) — v2

**Deliverable:** `assets/red-devilry-promo.mp4` — 47.0 s, 1080×1080 @ 30 fps, H.264 + AAC, loudness-normalized (−14 LUFS, true-peak −1 dB).
**Call to action:** `discord.gg/RedDevils`

## Concept
A 47-second recruitment trailer for the **Red Devilry** crew, built for the
**WARDOGS** (Bulkhead / Team17) early-access community. Nine shots across eight
narration-synced beats: blurred-fill bat-signal cold open → two-shot game stakes
(key art + generated squad march) → flaming-skull sting into logo reveal → crew
creed → Mist the raccoon → flying-Mist air-support gag → recruitment push →
Discord end card.

## Beat sheet / narration
| # | Time (s) | Visual | Line |
|---|----------|--------|------|
| 1 | 0.0–2.5 | Bat-signal gag (`batsignalgif.gif`) over blurred-fill of itself + "THE SIGNAL IS LIT." | "The signal is lit." |
| 2 | 2.0–13.0 | WARDOGS "TIME TO SEED" key art zoom → crossfade to generated squad-march pan; "WARDOGS // BULKHEAD" + "100 PLAYERS. 3 TEAMS. ONE ZONE." | "A hundred dogs. Three teams. One zone. This is WARDOGS. All-out warfare on Bulkhead's frontier." |
| 3 | 12.6–17.1 | Generated flaming-skull sting, white-flash cut into `Red Devilry.png` logo reveal + "RED DEVILRY" | "And this, is RED DEVILRY." |
| 4 | 16.7–22.5 | Golden eagle emblem (`Apollopng.png`) push-in + "DISCIPLINE. LOYALTY. TEETH." | "We fly disciplined. We fight loud. We hold the hill until the servers smoke." |
| 5 | 22.0–28.5 | Mist the raccoon (`mist.png`) push-in + "MORALE OFFICER: MIST" / "YES, THAT'S A RACCOON. HE BITES." | "Morale officer? Yes. That's a raccoon. His name is Mist. He bites." |
| 6 | 28.1–30.7 | "Thank you for flying with Mist" gag, profanity band cropped, blurred fill + "AIR SUPPORT: ALSO MIST." | (music sting) |
| 7 | 30.2–38.4 | Key-art lateral pan + "RECRUITMENT OPEN" / "PILOTS - MEDICS - MANIACS. BRING YOUR RAGE." | "Recruitment is open. Pilots, medics, maniacs. Bring your rage. Leave your ego." |
| 8 | 37.9–47.0 | End card: logo + "JOIN THE WING" + `DISCORD.GG/REDDEVILS` pill + "WARDOGS EARLY ACCESS - TIME TO SEED" | "Join the wing. Discord dot GG, slash Red Devils. Red Devilry. Time to seed." |

Game facts in the copy (100 players, three teams, one control zone) come from
Bulkhead/Team17 WARDOGS coverage; "TIME TO SEED" is the key-art tagline.

## Source assets (from github.com/Goldenapollo7/Main)
Downloaded at production time into `assets/reddevils/` (git-ignored scratch;
originals live in the Main repo): `Red Devilry.png` (hero logo), `Red Devilry.jpg`,
`Apollopng.png` (eagle emblem), `seeding.png` (WARDOGS key art), `mist.png`
(Mist the raccoon), `batsignalgif.gif` (signal cold-open),
`Thank you for flying with Mist.gif` (air-support gag — bottom caption band,
which carries a burned-in profanity, is cropped out in-scene).
Supplemental art generated at production time (also scratch, not committed):
`gen_squad.png` (squad march cutaway), `gen_skullfire.png` (flaming-skull sting).

## Production pipeline (zero paid API keys)
- **Narration:** on-platform voice audition → one TTS clip per beat (`vidtools/work/vo/n1..n7.mp3`).
- **Typography:** Black Ops One + Rajdhani (OFL) rendered to alpha plates with
  ImageMagick (the ffmpeg static build lacks `drawtext`); auto-fit sizing per plate.
- **Motion/comp:** FFmpeg 7 static — `zoompan` push-ins/pans, inner-scene `xfade`
  cutaways, beat-cut `xfade` transitions (fadeblack / fadewhite / circleopen),
  blurred-fill framing for portrait clips, `overlay` plates, `noise` + `vignette` grade.
- **Music bed:** fully synthesized in FFmpeg — sub-bass drone, brown-noise air,
  49 Hz pulse that goes double-time at the air-support gag, braam hits on every
  cut, a 2.2 s chirp riser into the logo reveal and a sub drop under it,
  final hit on the end card; mixed under the narration, `alimiter` + `loudnorm`
  (I=−14, TP=−1).
- **QC:** full-stream decode (1402/1402 frames), seek probes at all nine shots,
  `astats` peak check (−0.78 dBTP), frame grabs at every beat.

## Reproduce
```bash
pip install --user imageio-ffmpeg     # provides the static ffmpeg binary
ln -s "$(python3 -c 'import imageio_ffmpeg; print(imageio_ffmpeg.get_ffmpeg_exe())')" vidtools/ffmpeg
cd vidtools && bash make_plates.sh && python3 build_promo2.py
```
`build_promo2.py` re-probes narration durations, re-derives scene timings,
renders the eight scenes, xfade-concats them and mixes the final audio to
`vidtools/work/red-devilry-promo-v2.mp4` (~2.5 min of compute).
