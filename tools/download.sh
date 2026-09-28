#!/usr/bin/env bash
# Скачать видео с YouTube / Instagram до 1080p в mp4 (нужен yt-dlp: brew install yt-dlp).
# Пример: tools/download.sh "https://www.youtube.com/watch?v=x9yop0nYR9g" original.mp4
set -euo pipefail
[ $# -eq 2 ] || { echo "использование: $0 ссылка выход.mp4"; exit 1; }
yt-dlp -q --no-warnings -f "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]" \
  --merge-output-format mp4 -o "$2" "$1"
echo "скачано: $2"
