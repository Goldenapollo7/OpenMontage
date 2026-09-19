#!/usr/bin/env python3
"""Red Devilry promo builder — renders 7 scenes, xfade-concats, mixes narration + synth bed."""
import subprocess, os, sys, json

ROOT = "/home/user/OpenMontage"
V = f"{ROOT}/vidtools"
FF = f"{V}/ffmpeg"
A = f"{ROOT}/assets/reddevils"
P = f"{V}/work/plates"
VO = f"{V}/work/vo"
SC = f"{V}/work/scenes"
os.makedirs(SC, exist_ok=True)

FPS = 30
X = 0.5          # xfade duration
LEAD = 0.3       # visual lead before each voice line
GAP = 0.7        # tail after voice in scenes 1-6
TAIL7 = 1.8

def dur(path):
    out = subprocess.run([FF, "-i", path], capture_output=True, text=True).stderr
    for line in out.splitlines():
        if "Duration" in line:
            t = line.split("Duration:")[1].split(",")[0].strip()
            h, m, s = t.split(":")
            return float(h) * 3600 + float(m) * 60 + float(s)
    raise RuntimeError(f"no duration for {path}")

d = [dur(f"{VO}/n{i}.mp3") for i in range(1, 8)]
L = [LEAD + d[i] + (GAP if i < 6 else TAIL7) for i in range(7)]
start = [0.0]
for i in range(6):
    start.append(start[-1] + L[i] - X)
TOTAL = start[6] + L[6]
OFF = [s + LEAD for s in start]
print("durations:", [round(x, 2) for x in d])
print("scene L:", [round(x, 2) for x in L])
print("starts:", [round(x, 2) for x in start], "total", round(TOTAL, 2))

def run(cmd):
    r = subprocess.run(cmd, capture_output=True, text=True)
    if r.returncode != 0:
        print(r.stderr[-3000:])
        sys.exit(f"ffmpeg failed: {' '.join(cmd[:8])}...")
    return r

ZP = "x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=1080x1080:fps=30"

scenes = []

# S1 bat-signal
scenes.append(dict(
    inputs=[("-loop", "1", "-t", L[0], "-r", FPS, "-i", f"{P}/bg_radial_red.png"),
            ("-stream_loop", "-1", "-t", L[0], "-i", f"{A}/batsignalgif.gif"),
            ("-i", f"{P}/t_signal.png")],
    fc=f"[0:v]scale=1080:1080,setsar=1[bg];"
       f"[1:v]fps=30,scale=-2:760,setsar=1[g];"
       f"[bg][g]overlay=(W-w)/2:(H-h)/2-60[v1];"
       f"[v1][2:v]overlay=(W-w)/2:880[v2];"
       f"[v2]noise=alls=5:allf=t,vignette=angle=PI/5,format=yuv420p,fps=30[vout]"))

# S2 wardogs zoom
fr2 = int(L[1] * FPS)
scenes.append(dict(
    inputs=[("-loop", "1", "-t", L[1], "-r", FPS, "-i", f"{A}/seeding.png"),
            ("-i", f"{P}/topramp.png"), ("-i", f"{P}/t_kicker.png"),
            ("-i", f"{P}/lowerthird.png"), ("-i", f"{P}/t_zone.png")],
    fc=f"[0:v]scale=1620:1620,setsar=1[big];"
       f"[big]zoompan=z='1+0.22*on/{fr2}':d=1:{ZP}[z];"
       f"[z][1:v]overlay=0:0[a];[a][2:v]overlay=(W-w)/2:60[b];"
       f"[b][3:v]overlay=0:H-420[c];[c][4:v]overlay=(W-w)/2:900[v2];"
       f"[v2]vignette=angle=PI/6,format=yuv420p,fps=30[vout]"))

# S3 logo reveal + red flash
fr3 = int(L[2] * FPS)
scenes.append(dict(
    inputs=[("-loop", "1", "-t", L[2], "-r", FPS, "-i", f"{P}/bg_radial_red.png"),
            ("-i", f"{A}/Red_Devilry.png"),
            ("-f", "lavfi", "-t", L[2], "-i", f"color=c=0x9a1018:s=1080x1080:r={FPS}"),
            ("-i", f"{P}/t_logo.png")],
    fc=f"[0:v]scale=1080:1080,setsar=1[bg];"
       f"[1:v]scale=780:-2,setsar=1[lg];"
       f"[bg][lg]overlay=(W-w)/2:(H-h)/2-50,fps=30[c];"
       f"[c]zoompan=z='1.12-0.10*on/{fr3}':d=1:{ZP}[z];"
       f"[2:v]format=rgba,fade=t=out:st=0:d=0.5:alpha=1[fl];"
       f"[z][fl]overlay=0:0[v1];[v1][3:v]overlay=(W-w)/2:840[v2];"
       f"[v2]format=yuv420p,fps=30[vout]"))

# S4 apollo motto
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

# S5 mist (raccoon still, slow push-in)
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

# S6 wardogs pan
fr6 = int(L[5] * FPS)
scenes.append(dict(
    inputs=[("-loop", "1", "-t", L[5], "-r", FPS, "-i", f"{A}/seeding.png"),
            ("-i", f"{P}/topramp.png"), ("-i", f"{P}/t_recruit.png"),
            ("-i", f"{P}/lowerthird.png"), ("-i", f"{P}/t_roles.png")],
    fc=f"[0:v]scale=1944:1944,setsar=1[big];"
       f"[big]zoompan=z='1.35':d=1:x='(iw-iw/zoom)*on/{fr6}':y='ih/2-(ih/zoom/2)':s=1080x1080:fps=30[z];"
       f"[z][1:v]overlay=0:0[a];[a][2:v]overlay=(W-w)/2:60[b];"
       f"[b][3:v]overlay=0:H-420[c];[c][4:v]overlay=(W-w)/2:940[v2];"
       f"[v2]vignette=angle=PI/6,format=yuv420p,fps=30[vout]"))

# S7 end card
scenes.append(dict(
    inputs=[("-loop", "1", "-t", L[6], "-r", FPS, "-i", f"{P}/bg_radial_red.png"),
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

# ---- final assembly: xfade chain + audio ----
inputs = []
for i in range(1, 8):
    inputs += ["-i", f"{SC}/s{i}.mp4"]
for i in range(1, 8):
    inputs += ["-i", f"{VO}/n{i}.mp3"]

tr = ["fadeblack", "fadewhite", "fadeblack", "fade", "fadeblack", "fadeblack"]
fc = []
prev = "[0:v]"
for k in range(6):
    nxt = f"[{k+1}:v]"
    outl = f"[x{k}]" if k < 5 else "[v]"
    fc.append(f"{prev}{nxt}xfade=transition={tr[k]}:duration={X}:offset={round(start[k+1],3)}{outl}")
    prev = outl

# narration with offsets
for i in range(7):
    fc.append(f"[{7+i}:a]adelay=delays={int(OFF[i]*1000)}:all=1[a{i}]")
fc.append("".join(f"[a{i}]" for i in range(7)) + "amix=inputs=7:normalize=0[narr]")
# synth bed
T = round(TOTAL + 0.2, 2)
fc.append(f"aevalsrc='0.13*sin(2*PI*55*t)+0.08*sin(2*PI*82.41*t)+0.05*sin(2*PI*110*t)':d={T},lowpass=f=260,volume=eval=frame:volume='0.8+0.2*sin(2*PI*0.08*t)'[dr]")
fc.append(f"aevalsrc='0.32*exp(-2.5*mod(t,1.5))*sin(2*PI*49*t)':d={T}[pu]")
fc.append(f"anoisesrc=d={T}:c=brown:a=0.02[air]")
for k in range(1, 7):
    fc.append(f"aevalsrc='0.7*exp(-1.8*t)*sin(2*PI*46*t)+0.3*exp(-1.8*t)*sin(2*PI*69*t)':d=2.5,adelay=delays={int(start[k]*1000)}:all=1[b{k}]")
fc.append("[dr][pu][air]" + "".join(f"[b{k}]" for k in range(1, 7)) + "amix=inputs=9:normalize=0,volume=0.9[bed]")
fc.append("[narr]volume=1.2[nv]")
fc.append("[nv][bed]amix=inputs=2:normalize=0[mx]")
fc.append("[mx]alimiter=limit=0.95,loudnorm=I=-14:TP=-1.0:LRA=11[aout]")

out = f"{V}/work/red-devilry-promo.mp4"
cmd = [FF, "-y", "-loglevel", "error"] + inputs + [
    "-filter_complex", ";".join(fc), "-map", "[v]", "-map", "[aout]",
    "-c:v", "libx264", "-crf", "19", "-preset", "medium", "-pix_fmt", "yuv420p",
    "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-movflags", "+faststart", out]
print("final assembly ...")
run(cmd)
print("DONE", out, round(dur(out), 2))
json.dump(dict(durations=d, starts=start, offsets=OFF, total=TOTAL), open(f"{V}/work/timing.json", "w"), indent=1)
