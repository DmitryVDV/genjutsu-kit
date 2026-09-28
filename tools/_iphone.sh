# Общие настройки: так видео берёт галерея айфона (H.264 High 4.1, 24 кадра/с ровно, AAC 48 кГц).
IPHONE_V="-c:v libx264 -profile:v high -level:v 4.1 -pix_fmt yuv420p -crf 17 -preset slow -fps_mode cfr -color_primaries bt709 -color_trc bt709 -colorspace bt709 -tag:v avc1"
IPHONE_A="-c:a aac -b:a 192k -ar 48000 -ac 2"
IPHONE_MUX="-movflags +faststart"
