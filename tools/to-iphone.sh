#!/usr/bin/env bash
# Пережать видео так, чтобы его приняла галерея айфона. Рядом появится <имя>-iphone.mp4.
# Пример: tools/to-iphone.sh genjutsu/hotel-lobby/final-*.mp4
set -euo pipefail
. "$(dirname "$0")/_iphone.sh"
[ $# -ge 1 ] || { echo "использование: $0 файл.mp4 [ещё файлы…]"; exit 1; }
for f in "$@"; do
  out="${f%.*}-iphone.mp4"
  ffmpeg -y -v error -i "$f" -vf "fps=24,setsar=1" $IPHONE_V $IPHONE_A $IPHONE_MUX "$out"
  echo "для айфона: $out"
done
