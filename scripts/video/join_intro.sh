#!/bin/sh
# join_intro.sh: put the 6 s Flow/HyperFrames intro in front of the real-app walkthrough.
# Video: 0.5 s cross-dissolve from 5.5 to 6.0 s (video-director plan, 11 Nov 2026).
# Audio: the walkthrough's music bed (Clocked film bed.wav) leads in under the intro at about -20 LUFS
# (below the narrated -16 LUFS), fading up over 1 s, then a 0.5 s crossfade into the walkthrough's own mix,
# which is left exactly as it was (no second normalisation).
# Usage: scripts/video/join_intro.sh INTRO.mp4 WALKTHROUGH.mp4 OUT.mp4
set -eu
INTRO=$1 WALK=$2 OUT=$3
BED="$HOME/Projects/hack-clocked/video/film/assets/audio/bed.wav"
[ -f "$BED" ] || { echo "join_intro.sh: music bed not found: $BED" >&2; exit 1; }
ffmpeg -v error -y -i "$INTRO" -i "$WALK" -i "$BED" -filter_complex "
  [0:v]fps=30,scale=1920:1080,setsar=1,format=yuv420p[v0];
  [1:v]fps=30,scale=1920:1080,setsar=1,format=yuv420p[v1];
  [v0][v1]xfade=transition=fade:duration=0.5:offset=5.5[v];
  [2:a]atrim=0:6,asetpts=PTS-STARTPTS,volume=0.16,volume=29.2dB,alimiter=limit=0.89,afade=t=in:d=1,aresample=48000,aformat=channel_layouts=stereo[lead];
  [1:a]aresample=48000,aformat=channel_layouts=stereo[wa];
  [lead][wa]acrossfade=d=0.5:c1=tri:c2=tri[a]" \
  -map "[v]" -map "[a]" -c:v libx264 -preset medium -crf 18 -r 30 -c:a aac -b:a 192k -ar 48000 -movflags +faststart "$OUT"
echo "joined: $OUT"
