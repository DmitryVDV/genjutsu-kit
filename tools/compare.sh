#!/usr/bin/env bash
# Сравнение «оригинал над результатом» (для вертикального видео — рядом). Сразу в формате айфона.
# Пример: tools/compare.sh genjutsu/hotel-lobby/original.mp4 genjutsu/hotel-lobby/final.mp4 12 14.9 compare.mp4
set -euo pipefail
. "$(dirname "$0")/_iphone.sh"
[ $# -eq 5 ] || { echo "использование: $0 оригинал.mp4 результат.mp4 начало_с длина_с выход.mp4"; exit 1; }
orig=$1; res=$2; start=$3; dur=$4; out=$5
w=$(ffprobe -v error -select_streams v:0 -show_entries stream=width -of csv=p=0 "$res")
h=$(ffprobe -v error -select_streams v:0 -show_entries stream=height -of csv=p=0 "$res")
if [ "$w" -ge "$h" ]; then sc="960:-2"; st=vstack; else sc="-2:960"; st=hstack; fi
ffmpeg -y -v error -ss "$start" -t "$dur" -i "$orig" -i "$res" -filter_complex \
  "[0:v]fps=24,scale=$sc,setsar=1[a];[1:v]fps=24,scale=$sc,setsar=1[b];[a][b]$st[v]" \
  -map "[v]" -map "1:a?" $IPHONE_V $IPHONE_A $IPHONE_MUX -shortest "$out"
echo "сравнение: $out"
