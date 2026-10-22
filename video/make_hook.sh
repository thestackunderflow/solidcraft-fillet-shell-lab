#!/usr/bin/env sh
# Hook stills for the video and its Short, made from frame0-both-boxes.png (SolidCraft's own render) by adding words only:
# the tags ✗ REFUSED / ✓ BUILT, the order of each box, and the "edges highlighted" disclosure. No pixel of the render
# is repainted. Needs ffmpeg + DejaVu fonts (the video-qa image has both):
#   docker run --rm -v <lab>:/work -w /work video-qa:2 sh video/make_hook.sh
set -eu
F=video/frames
B=/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf
R=/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf
RED=0xb71c1c; GREEN=0x1b5e20; INK=0x1f2937
# landscape 1920x1080: tags above the left box and below the right box, disclosure at the bottom
ffmpeg -v error -y -i $F/frame0-both-boxes.png -vf "\
drawtext=fontfile=$B:text='✗ REFUSED':fontcolor=$RED:fontsize=64:x=520:y=120,\
drawtext=fontfile=$R:text='hollow first, then round':fontcolor=$INK:fontsize=38:x=522:y=196,\
drawtext=fontfile=$B:text='✓ BUILT':fontcolor=$GREEN:fontsize=64:x=980:y=860,\
drawtext=fontfile=$R:text='round first, then hollow':fontcolor=$INK:fontsize=38:x=982:y=936,\
drawtext=fontfile=$R:text='Same box, same 10 mm corners · SolidCraft 0.17.0 render · red\: edges highlighted by us':fontcolor=$INK:fontsize=28:x=(w-text_w)/2:y=1030" \
  $F/hook-landscape.png
# vertical 1080x1920 for the Short: the two single-box renders (iso-shell-only = the hollow box before the refused
# rounding step, iso-FS-10 = round first), same iso view, stacked; no highlight rods here, so no disclosure is needed
ffmpeg -v error -y -i $F/iso-shell-only.png -i $F/iso-FS-10.png -filter_complex "[0:v]crop=880:720:360:140,scale=800:-2[a];[1:v]crop=880:720:360:140,scale=800:-2[b];color=c=0xeef1f5:s=1080x1920[bg];[bg][a]overlay=140:330[t];[t][b]overlay=140:1170,drawtext=fontfile=$B:text='✗ REFUSED':fontcolor=$RED:fontsize=80:x=(w-text_w)/2:y=140,drawtext=fontfile=$R:text='hollow first, then round':fontcolor=$INK:fontsize=46:x=(w-text_w)/2:y=240,drawtext=fontfile=$B:text='✓ BUILT':fontcolor=$GREEN:fontsize=80:x=(w-text_w)/2:y=990,drawtext=fontfile=$R:text='round first, then hollow':fontcolor=$INK:fontsize=46:x=(w-text_w)/2:y=1090,drawtext=fontfile=$R:text='SolidCraft 0.17.0 renders, same iso view':fontcolor=$INK:fontsize=32:x=(w-text_w)/2:y=1850"   -frames:v 1 $F/hook-vertical.png
echo "wrote $F/hook-landscape.png $F/hook-vertical.png"
