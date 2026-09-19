#!/usr/bin/env python3
"""Red Devilry promo v2 — 8 scenes, cutaways, blurred-fill, riser/drop score."""
import subprocess, os, sys, json

ROOT = "/home/user/OpenMontage"
V = f"{ROOT}/vidtools"
FF = f"{V}/ffmpeg"
A = f"{ROOT}/assets/reddevils"
P = f"{V}/work/plates"
VO = f"{V}/work/vo"
SC = f"{V}/work/scenes2"
os.makedirs(SC, exist_ok=True)

FPS = 30
X = 0.5
LEAD = 0.3
GAP = 0.7
TAIL_END = 1.8

def dur(path):
    out = subprocess.run([FF, "-i", path], capture_output=True, text=True).stderr
    for line in out.splitlines():
        if "Duration" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return float(h) * 3600 + float(m) * 60 + float(s)
    raise RuntimeError(f"no duration for {path}")

d = [dur(f"{VO}/n{i}.mp3") for i in range(1, 8)]
# scenes: (narration index or None, length)
Lbase = [LEAD + d[i] + GAP for i in range(6)] + [LEAD + d[6] + TAIL_END]
scene_def = [
    dict(narr=0, L=Lbase[0]),          # 1 bat signal
    dict(narr=1, L=Lbase[1]),          # 2 wardogs two-shot
    dict(narr=2, L=Lbase[2] + 0.7),    # 3 skullfire sting + logo
    dict(narr=3, L=Lbase[3]),          # 4 apollo
    dict(narr=4, L=Lbase[4]),          # 5 raccoon
    dict(narr=None, L=2.6),            # 6 flying mist gag
    dict(narr=5, L=Lbase[5]),          # 7 recruitment pan
    dict(narr=6, L=Lbase[6]),          # 8 end card
]
L = [s["L"] for s in scene_def]
start = [0.0]
for i in range(len(L) - 1):
    start.append(start[-1] + L[i] - X)
TOTAL = start[-1] + L[-1]
OFF = [start[i] + LEAD for i, s in enumerate(scene_def) if s["narr"] is not None]
print("starts:", [round(x, 2) for x in start], "total", round(TOTAL, 2))

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        sys.exit("ffmpeg failed")
    return r

ZP = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1080:fps=30"

scenes = []

# S1 bat-signal, blurred fill
scenes.append(dict(
    inputs=[("-stream_loop", "-1", "-t", L[0], "-i", f"{A}/batsignalgif.gif"),
            ("-i", f"{P}/t_signal.png")],
    fc=f"[0:v]fps=30,split[a][b];"
       f"[a]scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080,gblur=sigma=22,eq=brightness=-0.28:saturation=1.2[bg];"
       f"[b]scale=-2:780,setsar=1[g];"
       f"[bg][g]overlay=(W-w)/2:(H-h)/2-50[v1];"
       f"[v1][1:v]overlay=(W-w)/2:880[v2];"
       f"[v2]noise=alls=5:allf=t,vignette=angle=PI/5,format=yuv420p,fps=30[vout]"))

# S2 wardogs two-shot: key art zoom -> generated squad pan
pA = round(L[1] * 0.55, 2)
pB = round(L[1] - pA + X, 2)
frA = int(pA * FPS)
frB = int(pB * FPS)
scenes.append(dict(
    inputs=[("-loop", "1", "-t", pA, "-r", FPS, "-i", f"{A}/seeding.png"),
            ("-loop", "1", "-t", pB, "-r", FPS, "-i", f"{A}/gen_squad.png"),
            ("-i", f"{P}/topramp.png"), ("-i", f"{P}/t_kicker.png"),
            ("-i", f"{P}/lowerthird.png"), ("-i", f"{P}/t_zone.png")],
    fc=f"[0:v]scale=1620:1620,setsar=1[b0];"
       f"[b0]zoompan=z='1+0.18*on/{frA}':d=1:{ZP}[z0];"
       f"[1:v]scale=-2:1080,setsar=1[b1];"
       f"[b1]zoompan=z='1':d=1:x='(iw-1080)*on/{frB}':y='0':s=1080x1080:fps=30[z1];"
       f"[z0][z1]xfade=transition=fade:duration={X}:offset={round(pA - X, 2)}[z];"
       f"[z][2:v]overlay=0:0[a];[a][3:v]overlay=(W-w)/2:60[b];"
       f"[b][4:v]overlay=0:H-420[c];[c][5:v]overlay=(W-w)/2:900[v2];"
       f"[v2]vignette=angle=PI/6,format=yuv420p,fps=30[vout]"))

# S3 skullfire sting -> logo reveal
tA = 1.1
tB = round(L[2] - tA + 0.4, 2)
fr3a = int(tA * FPS)
fr3b = int(tB * FPS)
scenes.append(dict(
    inputs=[("-loop", "1", "-t", tA, "-r", FPS, "-i", f"{A}/gen_skullfire.png"),
            ("-loop", "1", "-t", tB, "-r", FPS, "-i", f"{P}/bg_radial_red.png"),
            ("-i", f"{A}/Red_Devilry.png"),
            ("-i", f"{P}/t_logo.png")],
    fc=f"[0:v]scale=1620:-2,setsar=1[s0];"
       f"[s0]zoompan=z='1+0.15*on/{fr3a}':d=1:{ZP}[z0];"
       f"[1:v]scale=1080:1080,setsar=1[bg];"
       f"[2:v]scale=780:-2,setsar=1[lg];"
       f"[bg][lg]overlay=(W-w)/2:(H-h)/2-50,fps=30[c];"
       f"[c]zoompan=z='1.12-0.10*on/{fr3b}':d=1:{ZP}[z1];"
       f"[z0][z1]xfade=transition=fadewhite:duration=0.4:offset=0.7[z];"
       f"[z][3:v]overlay=(W-w)/2:840[v2];"
       f"[v2]format=yuv420p,fps=30[vout]"))

# S4 apollo
fr4 = int(L[3] * FPS)
scenes.append(dict(
    inputs=[("-loop", "1", "-t", L[3], "-r", FPS, "-i", f"{P}/bg_steel.png"),
            ("-i", f"{A}/Apollopng.png"), ("-i", f"{P}/t_motto.png")],
    fc=f"[0:v]scale=1080:1080,setsar=1[bg];"
       f"[1:v]scale=660:-2,setsar=1[ap];"
       f"[bg][ap]overlay=(W-w)/2:(H-h)/2-60,fps=30[c];"
       f"[c]zoompan=z='1+0.10*on/{fr4}':d=1:{ZP}[z];"
       f"[z][2:v]overlay=(W-w)/2:880[v2];"
       f"[v2]noise=alls=4:allf=t,vignette=angle=PI/5,format=yuv420p,fps=30[vout]"))

# S5 raccoon push-in
fr5 = int(L[4] * FPS)
scenes.append(dict(
    inputs=[("-loop", "1", "-t", L[4], "-r", FPS, "-i", f"{P}/bg_steel.png"),
            ("-loop", "1", "-t", L[4], "-r", FPS, "-i", f"{A}/mist.png"),
            ("-i", f"{P}/t_mist.png"), ("-i", f"{P}/t_mist_sub.png")],
    fc=f"[0:v]scale=1080:1080,setsar=1[bg];"
       f"[1:v]scale=-2:700,setsar=1[g];"
       f"[bg][g]overlay=(W-w)/2:(H-h)/2+20,fps=30[c];"
       f"[c]zoompan=z='1+0.08*on/{fr5}':d=1:{ZP}[v1];"
       f"[v1][2:v]overlay=(W-w)/2:40[v2];"
       f"[v2][3:v]overlay=(W-w)/2:920[v3];"
       f"[v3]vignette=angle=PI/5,format=yuv420p,fps=30[vout]"))

# S6 flying-mist gag (profanity band cropped), blurred fill
scenes.append(dict(
    inputs=[("-stream_loop", "-1", "-t", L[5], "-i", f"{A}/Thank_you_for_flying_with_Mist.gif"),
            ("-i", f"{P}/t_airsup.png")],
    fc=f"[0:v]fps=30,crop=480:360:0:0,split[a][b];"
       f"[a]scale=1080:1080:force_original_aspect_ratio=increase,crop=1080:1080,gblur=sigma=22,eq=brightness=-0.28[bg];"
       f"[b]scale=-2:700,setsar=1[g];"
       f"[bg][g]overlay=(W-w)/2:(H-h)/2[v1];"
       f"[v1][1:v]overlay=(W-w)/2:900[v2];"
       f"[v2]vignette=angle=PI/5,format=yuv420p,fps=30[vout]"))

# S7 recruitment pan
fr7 = int(L[6] * FPS)
scenes.append(dict(
    inputs=[("-loop", "1", "-t", L[6], "-r", FPS, "-i", f"{A}/seeding.png"),
            ("-i", f"{P}/topramp.png"), ("-i", f"{P}/t_recruit.png"),
            ("-i", f"{P}/lowerthird.png"), ("-i", f"{P}/t_roles.png")],
    fc=f"[0:v]scale=1944:1944,setsar=1[big];"
       f"[big]zoompan=z='1.35':d=1:x='(iw-iw/zoom)*on/{fr7}':y='ih/2-(ih/zoom/2)':s=1080x1080:fps=30[z];"
       f"[z][1:v]overlay=0:0[a];[a][2:v]overlay=(W-w)/2:60[b];"
       f"[b][3:v]overlay=0:H-420[c];[c][4:v]overlay=(W-w)/2:940[v2];"
       f"[v2]vignette=angle=PI/6,format=yuv420p,fps=30[vout]"))

# S8 end card
scenes.append(dict(
    inputs=[("-loop", "1", "-t", L[7], "-r", FPS, "-i", f"{P}/bg_radial_red.png"),
            ("-i", f"{A}/Red_Devilry.png"), ("-i", f"{P}/t_join.png"),
            ("-i", f"{P}/t_discord.png"), ("-i", f"{P}/t_seed.png")],
    fc=f"[0:v]scale=1080:1080,setsar=1[bg];"
       f"[1:v]scale=560:-2,setsar=1[lg];"
       f"[bg][lg]overlay=(W-w)/2:40[v1];"
       f"[v1][2:v]overlay=(W-w)/2:640[v2];"
       f"[v2][3:v]overlay=(W-w)/2:830[v3];"
       f"[v3][4:v]overlay=(W-w)/2:960[v4];"
       f"[v4]noise=alls=4:allf=t,vignette=angle=PI/5,format=yuv420p,fps=30[vout]"))

for i, sc in enumerate(scenes, 1):
    out = f"{SC}/s{i}.mp4"
    cmd = [FF, "-y", "-loglevel", "error"]
    for tup in sc["inputs"]:
        cmd += [str(x) for x in tup]
    cmd += ["-filter_complex", sc["fc"], "-map", "[vout]",
            "-c:v", "libx264", "-crf", "18", "-preset", "medium",
            "-pix_fmt", "yuv420p", "-r", str(FPS), "-t", str(L[i - 1]), out]
    print("render scene", i, "...")
    run(cmd)
    print("  ok", round(dur(out), 2))

# ---- final assembly ----
inputs = []
for i in range(1, len(scenes) + 1):
    inputs += ["-i", f"{SC}/s{i}.mp4"]
for i in range(1, 8):
    inputs += ["-i", f"{VO}/n{i}.mp3"]

tr = ["fadeblack", "fadewhite", "fadeblack", "fade", "circleopen", "fadeblack", "fadeblack"]
fc = []
prev = "[0:v]"
for k in range(len(tr)):
    nxt = f"[{k+1}:v]"
    outl = f"[x{k}]" if k < len(tr) - 1 else "[v]"
    fc.append(f"{prev}{nxt}xfade=transition={tr[k]}:duration={X}:offset={round(start[k+1],3)}{outl}")
    prev = outl

for i in range(7):
    fc.append(f"[{len(scenes)+i}:a]adelay=delays={int(OFF[i]*1000)}:all=1[a{i}]")
fc.append("".join(f"[a{i}]" for i in range(7)) + "amix=inputs=7:normalize=0[narr]")

T = round(TOTAL + 0.2, 2)
ST6 = round(start[5], 2)
fc.append(f"aevalsrc='0.13*sin(2*PI*55*t)+0.08*sin(2*PI*82.41*t)+0.05*sin(2*PI*110*t)':d={T},lowpass=f=260,volume=eval=frame:volume='0.8+0.2*sin(2*PI*0.08*t)'[dr]")
fc.append(f"aevalsrc='0.32*exp(-2.5*if(lt(t,{ST6}),mod(t,1.5),mod(t,0.75)))*sin(2*PI*49*t)':d={T}[pu]")
fc.append(f"anoisesrc=d={T}:c=brown:a=0.02[air]")
for k in range(1, len(scenes)):
    fc.append(f"aevalsrc='0.7*exp(-1.8*t)*sin(2*PI*46*t)+0.3*exp(-1.8*t)*sin(2*PI*69*t)':d=2.5,adelay=delays={int(start[k]*1000)}:all=1[b{k}]")
# riser into logo reveal
fc.append(f"aevalsrc='0.11*sin(2*PI*(200*t+150*t*t))*min(1,t/1.6)':d=2.2,adelay=delays={int((start[2]-2.2)*1000)}:all=1[ris]")
# big drop at logo + final hit at end card
fc.append(f"aevalsrc='1.0*exp(-1.5*t)*sin(2*PI*40*t)+0.5*exp(-1.5*t)*sin(2*PI*60*t)':d=3,adelay=delays={int(start[2]*1000)}:all=1[drop]")
fc.append(f"aevalsrc='0.9*exp(-1.4*t)*sin(2*PI*42*t)+0.4*exp(-1.4*t)*sin(2*PI*63*t)':d=3,adelay=delays={int(start[7]*1000)}:all=1[fin]")
braams = "".join(f"[b{k}]" for k in range(1, len(scenes)))
fc.append(f"[dr][pu][air]{braams}[ris][drop][fin]amix=inputs={6 + (len(scenes)-1)}:normalize=0,volume=0.9[bed]")
fc.append("[narr]volume=1.2[nv]")
fc.append("[nv][bed]amix=inputs=2:normalize=0[mx]")
fc.append("[mx]alimiter=limit=0.95,loudnorm=I=-14:TP=-1.0:LRA=11[aout]")

out = f"{V}/work/red-devilry-promo-v2.mp4"
cmd = [FF, "-y", "-loglevel", "error"] + inputs + [
    "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[aout]",
    "-c:v", "libx264", "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out]
print("final assembly ...")
run(cmd)
print("DONE", out, round(dur(out), 2))
json.dump(dict(starts=start, offsets=OFF, total=TOTAL), open(f"{V}/work/timing2.json", "w"), indent=1)
