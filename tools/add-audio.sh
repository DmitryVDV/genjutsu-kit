#!/usr/bin/env bash
# Наложить звук оригинала на результат (кусок оригинала с той же секунды). Сразу в формате айфона.
# Пример: tools/add-audio.sh recast.mp4 original.mp4 12 14.9 final.mp4
set -euo pipefail
. "$(dirname "$0")/_iphone.sh"
[ $# -eq 5 ] || { echo "использование: $0 видео.mp4 оригинал.mp4 начало_с длина_с выход.mp4"; exit 1; }
ffmpeg -y -v error -i "$1" -ss "$3" -t "$4" -i "$2" -map 0:v -map "1:a?" -vf "fps=24,setsar=1" \
  $IPHONE_V $IPHONE_A $IPHONE_MUX -shortest "$5"
echo "со звуком оригинала: $5"
