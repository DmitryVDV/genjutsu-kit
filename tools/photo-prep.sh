#!/usr/bin/env bash
# Подготовить селфи: HEIC → JPEG и, если задано, вырезать лицо крупно (второй референс сходства).
# Пример: tools/photo-prep.sh IMG_7227.heic selfie.jpg              — только перевести в JPEG
#         tools/photo-prep.sh IMG_7227.heic face.jpg 560:660:20:1330 — ещё и вырезать (w:h:x:y)
set -euo pipefail
[ $# -ge 2 ] || { echo "использование: $0 фото выход.jpg [w:h:x:y]"; exit 1; }
src=$1
case "$(printf %s "$src" | tr "[:upper:]" "[:lower:]")" in
  *.heic|*.heif)
    tmp="$(mktemp -d)/src.jpg"
    if command -v sips >/dev/null; then sips -s format jpeg "$src" --out "$tmp" >/dev/null
    else heif-convert "$src" "$tmp" >/dev/null; fi   # Linux: apt install libheif-examples
    src=$tmp ;;
esac
if [ $# -eq 3 ]; then ffmpeg -y -v error -i "$src" -vf "crop=$3" -q:v 2 "$2"
else ffmpeg -y -v error -i "$src" -q:v 2 "$2"; fi
echo "готово: $2"
