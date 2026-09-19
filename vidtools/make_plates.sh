#!/bin/bash
set -e
cd /home/user/OpenMontage/vidtools
mkdir -p work/plates
P=work/plates
B=BlackOpsOne-Regular.ttf
RS=Rajdhani-SemiBold.ttf
STEEL="#e8e6e3"
BRED="#ff2038"

fitplate() { # name font maxsize fill stroke sw text maxw h kern
  local name=$1 font=$2 maxsize=$3 fill=$4 stroke=$5 sw=$6 text=$7 maxw=${8:-1000} h=${9:-300} kern=${10:-0}
  local size=$maxsize
  local w=$(convert -font $font -kerning $kern -pointsize $size -stroke none label:"$text" -format "%w" info:)
  if [ "$w" -gt "$maxw" ]; then size=$(( size * maxw / w )); fi
  if [ "$sw" != "0" ]; then
    convert -size 1080x$h xc:none -font $font -kerning $kern -pointsize $size -fill "$fill" -stroke "$stroke" -strokewidth $sw -gravity center -annotate +0+0 "$text" -stroke none $P/$name.png
  else
    convert -size 1080x$h xc:none -font $font -kerning $kern -pointsize $size -fill "$fill" -gravity center -annotate +0+0 "$text" $P/$name.png
  fi
  echo "$name ${size}px"
}

fitplate t_signal   $B 84  "$STEEL" "#0a0a0a" 6 "THE SIGNAL IS LIT." 1000 160
fitplate t_kicker   $RS 58 "$BRED"  "#0a0a0a" 4 "WARDOGS  //  BULKHEAD" 1000 120 8
fitplate t_zone     $B 72  "$STEEL" "#0a0a0a" 6 "100 PLAYERS. 3 TEAMS. ONE ZONE." 1000 160
fitplate t_logo     $B 132 "$STEEL" "#0a0a0a" 8 "RED DEVILRY" 1020 220
fitplate t_motto    $B 74  "$STEEL" "#0a0a0a" 6 "DISCIPLINE. LOYALTY. TEETH." 1000 160
fitplate t_mist     $B 78  "$STEEL" "#0a0a0a" 6 "MORALE OFFICER: MIST" 1000 160
fitplate t_mist_sub $RS 50 "#ffd9a0" "#0a0a0a" 4 "YES, THAT’S A RACCOON. HE BITES." 1000 120
fitplate t_recruit  $B 96  "$BRED"  "#0a0a0a" 7 "RECRUITMENT OPEN" 1000 180
fitplate t_roles    $RS 50 "$STEEL" "#0a0a0a" 4 "PILOTS - MEDICS - MANIACS. BRING YOUR RAGE." 1000 120
fitplate t_join     $B 108 "$STEEL" "#0a0a0a" 8 "JOIN THE WING" 1000 180
fitplate t_seed     $RS 52 "#ffb347" "#0a0a0a" 4 "WARDOGS EARLY ACCESS  -  TIME TO SEED" 1000 120 4

convert -size 960x150 xc:none -fill "#c8102e" -stroke "$STEEL" -strokewidth 5 \
  -draw "roundrectangle 3,3 956,146 26,26" \
  -font $B -pointsize 66 -fill "#ffffff" -gravity center -annotate +0+2 "DISCORD.GG/REDDEVILS" \
  $P/t_discord.png
echo "t_discord"

convert -size 1080x1080 radial-gradient:"#4a0d12"-"#050404" $P/bg_radial_red.png
convert -size 1080x1080 radial-gradient:"#232a33"-"#04050a" $P/bg_steel.png
convert -size 1080x420 xc:black -size 1080x420 gradient:gray\(0\)-gray\(255\) -compose CopyOpacity -composite $P/lowerthird.png
convert -size 1080x220 xc:black -size 1080x220 gradient:gray\(255\)-gray\(0\) -compose CopyOpacity -composite $P/topramp.png
echo "backgrounds done"
