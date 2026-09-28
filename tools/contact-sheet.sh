#!/usr/bin/env bash
# Лист кадров 4×3 из куска видео и время резов (смены плана) — посмотреть глазами без плеера.
# Пример: tools/contact-sheet.sh original.mp4 12 15 sheet.jpg
set -euo pipefail
[ $# -eq 4 ] || { echo "использование: $0 видео.mp4 начало_с длина_с лист.jpg"; exit 1; }
step=$(python3 -c "print(max($3/12, 0.5))")
ffmpeg -y -v error -ss "$2" -t "$3" -i "$1" -vf "fps=1/$step,scale=480:-1,tile=4x3" -frames:v 1 "$4"
echo "лист кадров: $4 (кадр каждые ${step} с)"
echo -n "резы, с от начала куска: "
ffmpeg -v error -ss "$2" -t "$3" -i "$1" -vf "select='gt(scene,0.3)',metadata=print:file=-" -f null - \
  | grep -o 'pts_time:[0-9.]*' | cut -d: -f2 | tr '\n' ' '; echo
