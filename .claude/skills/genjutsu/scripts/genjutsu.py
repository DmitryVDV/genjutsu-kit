#!/usr/bin/env python3
"""Аналог Higgsfield Genjutsu через API fal: движение из чужого видео, персонаж — из референсов.

Самостоятельный скрипт: только stdlib Python ≥ 3.9 + ffmpeg/ffprobe (+ yt-dlp для ссылок).
Команды (платные без --yes только печатают план и цену и ничего не тратят):
    check   — что установлено, есть ли ключ fal, куда пишутся результаты
    status  — что уже сделано и можно переиспользовать: исходники, аватары, прогоны, итоги
    fetch   — скачать видео по ссылке или взять файл, лист кадров и время резов
    avatar  — референсы персонажа из селфи (GPT Image 2 edit): лицо, рост, лист персонажа   [платно]
    scene   — кадр исходника с персонажем вместо исполнителя                              [платно]
    recast  — перекаст куска видео (Kling O3 edit по умолчанию; Seedance — для выдуманных) [платно]
    splice  — вклеить исправленный кусок в клип по времени реза
    finish  — итог: клип со звуком оригинала и, по желанию, сравнение «оригинал над результатом»
    iphone  — пережать любой готовый файл под галерею айфона (finish делает это сам)

Ключ: переменная окружения FAL_KEY (или FALAI_API_KEY) либо строка FAL_KEY=… в .env текущей папки.
Результаты: $GENJUTSU_DIR, иначе content/genjutsu/ (если есть content/), иначе ./genjutsu/.
"""
from __future__ import annotations

import argparse
import json
import mimetypes
import os
import re
import shutil
import subprocess
import sys
import time
import urllib.error
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

ROOT = Path.cwd()
REST = "https://rest.fal.ai"
QUEUE = "https://queue.fal.run"
KEY_NAMES = ("FAL_KEY", "FALAI_API_KEY")
SEEDANCE = "bytedance/seedance-2.5/reference-to-video"
IMAGE_MODEL = "openai/gpt-image-2/edit"


def work_dir() -> Path:
    if os.environ.get("GENJUTSU_DIR"):
        return Path(os.environ["GENJUTSU_DIR"])
    if (ROOT / "content").is_dir():
        return ROOT / "content" / "genjutsu"
    return ROOT / "genjutsu"


WORK = work_dir()
LOG = WORK / "log.jsonl"

# Seedance 2.5 на fal, 25.09.2026: токены = w·h·(вход+выход)·24/1024, $0.0214 за 1000,
# с видеореференсом ×0.6. Картинки и звук не тарифицируются. Реальные лица НЕ принимает
# (content_policy_violation «likenesses of real people», 27.09) — только выдуманные персонажи.
TOKEN_USD = 0.0214 / 1000
VIDEO_REF_FACTOR = 0.6
VIDEO_MIN_S, VIDEO_MAX_S = 1.8, 30.2
MAX_IMAGES = 30
# Kling O3 edit, 27.09.2026: $0.168 за секунду выхода; видео 3–15 с, сторона ≥ 720 px;
# персонажей (elements) + картинок вместе ≤ 4. Реальные лица принимает.
KLING = "fal-ai/kling-video/o3/pro/video-to-video/edit"
KLING_USD_S = 0.168
KLING_MIN_S, KLING_MAX_S = 3.0, 15.0
KLING_SAFE_MAX_S = 14.9  # 15.0 после перекодирования выходит за предел
KLING_MAX_REFS = 4
KLING_MIN_SIDE = 720
UPLOAD_LIMIT = 90 * 1024 * 1024  # выше fal-js переходит на multipart — здесь его нет
# GPT Image 2 edit, high: 1024×1024 $0.219 (страница модели) — 1024×1536 ≈ $0.3
IMAGE_USD_HIGH = 0.30

SAME_PERSON = ("the exact same person as in the reference photos: same face, facial structure, "
               "skin texture, hairline, eye color, facial hair. No beautification, no retouching, "
               "no age change. Photorealistic, natural skin, sharp focus. No text, no labels.")
AVATAR_SHOTS = {
    "face": ({"width": 1024, "height": 1536},
             "Close-up portrait of " + SAME_PERSON + " Frontal, neutral expression, eyes to "
             "camera, head and shoulders, outfit: {outfit}. Soft even studio light, plain light-gray "
             "background."),
    "body": ({"width": 1024, "height": 1536},
             "Full-body photo of " + SAME_PERSON + " Standing straight, arms relaxed, whole body "
             "from head to shoes with margin around, realistic proportions, outfit: {outfit}. "
             "Even studio light, plain light-gray background."),
    "sheet": ({"width": 1536, "height": 1024},
              "Character reference sheet of " + SAME_PERSON + " Four full-body views side by "
              "side at the same scale: front, three-quarter, side profile, back. Outfit: {outfit}. "
              "Same even studio light, plain light-gray background."),
}
WARDROBE_NOTE = (" The LAST reference image is a wardrobe reference only: copy the clothing, "
                 "jewelry and accessories from it. Take nothing else from the person in it — not the "
                 "face, beard, hair, skin tone, sunglasses or body shape.")
SCENE_PROMPT = ("Image 1 is a frame from a video. Replace {who} with the person from the other "
                "images: same identity, keep the pose, gesture, framing, camera angle, lighting, "
                "background and every other person exactly as in Image 1. Photorealistic. No text.")
# Без этого абзаца Kling проводил руку сквозь лицо и путал пальцы (Hotel Lobby, 27.09); с ним — нет.
HANDS_BLOCK = ("HANDS ARE THE PRIORITY. Copy every hand and finger pose from @Video1 exactly: the "
               "same finger positions, the same crossed and interlocked fingers, the same contact "
               "points and the same timing. Each hand has exactly five fingers. When a hand comes up "
               "to the face it stays in front of the face and touches the mouth or chin exactly as "
               "in @Video1 — a hand never passes through the head or the face. No distorted, merged, "
               "bent-backwards or extra fingers.")

# Галерея айфона не берёт переменную частоту кадров (склейка 25 и 24 кадров дала 307200/1)
# и высокие уровни H.264. Все выходные файлы — с этими настройками.
IPHONE_FPS = 24
IPHONE_ARGS = ["-c:v", "libx264", "-profile:v", "high", "-level:v", "4.1", "-pix_fmt", "yuv420p",
               "-crf", "17", "-preset", "slow", "-fps_mode", "cfr",
               "-color_primaries", "bt709", "-color_trc", "bt709", "-colorspace", "bt709",
               "-c:a", "aac", "-b:a", "192k", "-ar", "48000", "-ac", "2",
               "-tag:v", "avc1", "-movflags", "+faststart"]

REF_RE = re.compile(r"@\s?(Image|Video|Element)\s?(\d+)", re.IGNORECASE)
PLACEHOLDER_RE = re.compile(r"\{[A-Z][A-Z0-9_]*\}")


# ---------- чистые функции (тесты — test_genjutsu.py) ----------

def out_dims(resolution: str, width: int, height: int) -> tuple[int, int]:
    """Размер выхода Seedance: короткая сторона = 480/720/1080, пропорция — как у исходника."""
    short = int(resolution.rstrip("p"))
    if width <= height:
        return short, round(short * height / width)
    return round(short * width / height), short


def seedance_usd(in_s: float, out_s: float, width: int, height: int) -> float:
    tokens = width * height * (in_s + out_s) * 24 / 1024
    return tokens * TOKEN_USD * VIDEO_REF_FACTOR


def with_hands(prompt: str, enabled: bool = True) -> str:
    """Дописать абзац про руки, если его в промпте ещё нет."""
    if not enabled or "HANDS ARE THE PRIORITY" in prompt.upper():
        return prompt
    return prompt.rstrip() + "\n" + HANDS_BLOCK


def ref_errors(prompt: str, n_images: int, n_elements: int = 0) -> list[str]:
    """Ссылки @Image N / @Element N / @Video N в промпте должны указывать на переданное."""
    errors = []
    videos = set()
    for kind, num in REF_RE.findall(prompt):
        n = int(num)
        if kind.lower() == "video":
            videos.add(n)
            if n != 1:
                errors.append(f"@Video {n}: видео одно, есть только @Video 1")
        elif kind.lower() == "element":
            if n < 1 or n > n_elements:
                errors.append(f"@Element {n}: персонажей передано {n_elements}")
        elif n < 1 or n > n_images:
            errors.append(f"@Image {n}: картинок передано {n_images}")
    if 1 not in videos:
        errors.append("в промпте нет @Video 1 — модель не узнает, что редактировать")
    for name in PLACEHOLDER_RE.findall(prompt):
        errors.append(f"не подставлено {name}: уточни у человека и впиши в промпт")
    return sorted(set(errors))


def recast_payload(prompt: str, video_url: str, image_urls: list, resolution: str,
                   audio: str, seed: int | None) -> dict:
    payload = {
        "prompt": prompt,
        "task": "editing",
        "video_urls": [video_url],
        "image_urls": list(image_urls),
        "resolution": resolution,
        "generate_audio": audio == "generated",
    }
    if seed is not None:
        payload["seed"] = seed
    return payload


def kling_payload(prompt: str, video_url: str, image_urls: list, elements: list,
                  audio: str) -> dict:
    """elements — список наборов URL на персонажа: первый — лицо спереди, остальные — референсы."""
    return {
        "prompt": prompt,
        "video_url": video_url,
        "image_urls": list(image_urls),
        "elements": [{"frontal_image_url": e[0], "reference_image_urls": list(e[1:])}
                     for e in elements],
        "keep_audio": audio == "original",
        "shot_type": "customize",
    }


def splice_plan(at: float, to: float, base_len: float) -> list[tuple[str, float, float]]:
    """Куски склейки: база до `at`, исправление на [at, to), база после `to`."""
    if not 0 <= at < to <= base_len:
        raise ValueError(f"нужно 0 ≤ at < to ≤ {base_len:.2f}, дано at={at}, to={to}")
    plan = []
    if at > 0:
        plan.append(("base", 0.0, at))
    plan.append(("fix", 0.0, to - at))
    if to < base_len:
        plan.append(("base", to, base_len))
    return plan


# ---------- fal: ключ, очередь, хранилище ----------

def read_key() -> str:
    for name in KEY_NAMES:
        if os.environ.get(name):
            return os.environ[name].strip()
    env = ROOT / ".env"
    if env.exists():
        for line in env.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            for name in KEY_NAMES:
                if line.startswith(name + "="):
                    key = line.split("=", 1)[1].strip().strip('"').strip("'")
                    if key:
                        return key
    sys.exit("нет ключа fal: добавь строку FAL_KEY=… в .env этой папки "
             "(ключ — https://fal.ai/dashboard/keys) или задай переменную FAL_KEY")


def has_key() -> bool:
    try:
        read_key()
        return True
    except SystemExit:
        return False


def http(method: str, url: str, key: str, body: dict | None = None) -> dict:
    data = json.dumps(body).encode("utf-8") if body is not None else None
    req = urllib.request.Request(url, data=data, method=method)
    req.add_header("Authorization", f"Key {key}")
    req.add_header("Accept", "application/json")
    if data is not None:
        req.add_header("Content-Type", "application/json")
    try:
        with urllib.request.urlopen(req, timeout=120) as resp:
            return json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as err:
        text = err.read().decode("utf-8", "replace")[:800]
        if "likenesses of real people" in text:
            text += ("\n→ Это Seedance: реальные лица не принимает. Запусти с --engine kling.")
        sys.exit(f"fal {method} {url.split('?')[0]} → HTTP {err.code}: {text}")


def submit_and_wait(model: str, payload: dict, key: str, poll: float = 5.0) -> dict:
    sub = http("POST", f"{QUEUE}/{model}", key, payload)
    rid = sub.get("request_id")
    status_url = sub.get("status_url") or f"{QUEUE}/{model}/requests/{rid}/status"
    response_url = sub.get("response_url") or f"{QUEUE}/{model}/requests/{rid}"
    print(f"request_id: {rid}", flush=True)
    started = time.time()
    last = None
    while True:
        status = http("GET", status_url, key).get("status")
        if status != last:
            print(f"  {status} · {int(time.time() - started)} с", flush=True)
            last = status
        if status == "COMPLETED":
            break
        if status in ("FAILED", "CANCELLED", "ERROR"):
            sys.exit(f"fal: запрос {rid} завершился как {status}")
        time.sleep(poll)
    result = http("GET", response_url, key)
    result["_request_id"] = rid
    result["_seconds"] = round(time.time() - started, 1)
    return result


def download(url: str, out: Path) -> None:
    out.parent.mkdir(parents=True, exist_ok=True)
    with urllib.request.urlopen(url, timeout=600) as resp, open(out, "wb") as fh:
        fh.write(resp.read())


def upload(path: Path, key: str) -> str:
    size = path.stat().st_size
    if size > UPLOAD_LIMIT:
        sys.exit(f"{path}: {size // 2**20} МБ — больше 90 МБ; укороти или пережми (--start/--duration)")
    ctype = mimetypes.guess_type(str(path))[0] or "application/octet-stream"
    init = http("POST", f"{REST}/storage/upload/initiate?storage_type=fal-cdn-v3", key,
                {"content_type": ctype, "file_name": path.name})
    req = urllib.request.Request(init["upload_url"], data=path.read_bytes(), method="PUT")
    req.add_header("Content-Type", ctype)
    with urllib.request.urlopen(req, timeout=600):
        pass
    print(f"  загружено: {path.name}", flush=True)
    return init["file_url"]


# ---------- ffmpeg и файлы ----------

def run(cmd: list) -> None:
    subprocess.run([str(c) for c in cmd], check=True)


def probe(path: Path) -> dict:
    out = subprocess.run(
        ["ffprobe", "-v", "error", "-select_streams", "v:0", "-show_entries",
         "stream=width,height:format=duration,size", "-of", "json", str(path)],
        check=True, capture_output=True, text=True).stdout
    data = json.loads(out)
    st = data["streams"][0]
    return {"width": int(st["width"]), "height": int(st["height"]),
            "duration": float(data["format"]["duration"]), "size": int(data["format"]["size"])}


def cut_times(path: Path, start: float, duration: float) -> list[float]:
    """Время резов (смены плана) внутри куска, в секундах от начала куска."""
    out = subprocess.run(
        ["ffmpeg", "-v", "error", "-ss", str(start), "-t", str(duration), "-i", str(path), "-vf",
         "select='gt(scene,0.3)',metadata=print:file=-", "-f", "null", "-"],
        capture_output=True, text=True).stdout
    return [round(float(m), 2) for m in re.findall(r"pts_time:([\d.]+)", out)]


def prepare_source(video: Path, start: float | None, duration: float | None, dest: Path) -> Path:
    """Вырезать кусок или пережать, если файл не годится для загрузки как есть."""
    info = probe(video)
    need = (start is not None or duration is not None or info["size"] > UPLOAD_LIMIT
            or video.suffix.lower() not in (".mp4", ".mov"))
    if not need:
        return video
    dest.parent.mkdir(parents=True, exist_ok=True)
    cmd = ["ffmpeg", "-y", "-v", "error"]
    if start is not None:
        cmd += ["-ss", start]
    cmd += ["-i", video]
    if duration is not None:
        cmd += ["-t", duration]
    cmd += ["-c:v", "libx264", "-crf", "18", "-preset", "medium", "-pix_fmt", "yuv420p",
            "-c:a", "aac", "-b:a", "192k", "-movflags", "+faststart", dest]
    run(cmd)
    return dest


def as_jpeg(path: Path, scratch: Path) -> Path:
    """HEIC с айфона → JPEG (sips на маке, иначе ffmpeg)."""
    if path.suffix.lower() not in (".heic", ".heif"):
        return path
    scratch.mkdir(parents=True, exist_ok=True)
    out = scratch / (path.stem + ".jpg")
    if shutil.which("sips"):
        subprocess.run(["sips", "-s", "format", "jpeg", "-Z", "2048", str(path), "--out", str(out)],
                       check=True, capture_output=True)
    else:
        run(["ffmpeg", "-y", "-v", "error", "-i", path, out])
    return out


def meta_path(clip: Path) -> Path:
    return clip.with_suffix(".json")


def write_meta(clip: Path, meta: dict) -> None:
    meta_path(clip).write_text(json.dumps(meta, ensure_ascii=False, indent=2), encoding="utf-8")


def read_meta(clip: Path) -> dict:
    p = meta_path(clip)
    if not p.exists():
        sys.exit(f"нет {p.name}: не знаю, из какого куска оригинала этот клип. "
                 "Передай --original/--start/--duration")
    return json.loads(p.read_text(encoding="utf-8"))


def log(entry: dict) -> None:
    LOG.parent.mkdir(parents=True, exist_ok=True)
    entry["at"] = datetime.now(timezone.utc).isoformat(timespec="seconds")
    with open(LOG, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(entry, ensure_ascii=False) + "\n")


def stamp() -> str:
    return datetime.now().strftime("%Y%m%d-%H%M%S")


def plan_only(args) -> bool:
    if not args.yes:
        print("это план: добавь --yes, чтобы запустить")
        return True
    return False


def image_call(prompt: str, files: list, size, quality: str, out: Path, key: str) -> dict:
    urls = [upload(Path(f), key) for f in files]
    res = submit_and_wait(IMAGE_MODEL, {"prompt": prompt, "image_urls": urls,
                                        "image_size": size, "quality": quality,
                                        "num_images": 1, "output_format": "png"}, key)
    images = res.get("images") or []
    if not images:
        sys.exit(f"в ответе нет images: {json.dumps(res)[:600]}")
    download(images[0]["url"], out)
    print(f"сохранено: {out}")
    return res


# ---------- команды ----------

def cmd_check(args) -> None:
    ok = True
    print(f"python {sys.version.split()[0]}")
    for tool, need in (("ffmpeg", True), ("ffprobe", True), ("yt-dlp", False)):
        path = shutil.which(tool)
        print(f"{tool}: {path or 'НЕТ'}" + ("" if path or need else "  (нужен только для ссылок)"))
        ok = ok and (bool(path) or not need)
    print(f"ключ fal: {'есть' if has_key() else 'НЕТ — строка FAL_KEY=… в .env или переменная FAL_KEY'}")
    print(f"результаты: {WORK}")
    if not ok:
        sys.exit("поставь недостающее: brew install ffmpeg yt-dlp (мак) / apt install ffmpeg")


def cmd_status(args) -> None:
    print(f"результаты: {WORK}")
    print(f"ключ fal: {'есть' if has_key() else 'НЕТ'}")
    avatars = sorted(d for d in (WORK / "_avatar").glob("*") if d.is_dir()) if (WORK / "_avatar").is_dir() else []
    print("аватары:" + ("" if avatars else " нет"))
    for a in avatars:
        shots = [s for s in AVATAR_SHOTS if (a / f"{s}.png").exists()]
        old = len(list(a.glob("*-2*.png")))
        print(f"  {a.name}: {', '.join(shots) or 'пусто'}" + (f" (+{old} прежних версий)" if old else ""))
    slugs = sorted(d for d in WORK.glob("*") if d.is_dir() and not d.name.startswith("_")) if WORK.is_dir() else []
    print("ролики:" + ("" if slugs else " нет"))
    for d in slugs:
        parts = []
        if (d / "original.mp4").exists():
            parts.append("исходник")
        if (d / "prompt.txt").exists():
            parts.append("prompt.txt")
        recasts = sorted(d.rglob("recast-*.mp4"), key=lambda x: x.stat().st_mtime)
        finals = sorted(d.glob("final-*.mp4"), key=lambda x: x.stat().st_mtime)
        compares = sorted(d.glob("compare-*.mp4"), key=lambda x: x.stat().st_mtime)
        if recasts:
            parts.append(f"прогонов {len(recasts)} (последний {recasts[-1].name})")
        if finals:
            parts.append(f"итог {finals[-1].name}")
        if compares:
            parts.append(f"сравнение {compares[-1].name}")
        print(f"  {d.name}: {'; '.join(parts) or 'пусто'}")
    if LOG.exists():
        total = 0.0
        for line in LOG.read_text(encoding="utf-8").splitlines():
            e = json.loads(line)
            total += e.get("price_usd_est") or (IMAGE_USD_HIGH if e.get("kind") in ("avatar", "scene") else 0)
        print(f"потрачено по журналу ≈ ${total:.2f}")


def cmd_fetch(args) -> None:
    run_dir = WORK / args.slug
    run_dir.mkdir(parents=True, exist_ok=True)
    original = run_dir / "original.mp4"
    if args.url:
        if not shutil.which("yt-dlp"):
            sys.exit("нет yt-dlp: brew install yt-dlp")
        if original.exists():
            print(f"уже скачано: {original}")
        else:
            run(["yt-dlp", "-q", "--no-warnings", "-f",
                 "bv*[height<=1080][ext=mp4]+ba[ext=m4a]/b[height<=1080]",
                 "--merge-output-format", "mp4", "-o", original, args.url])
    else:
        shutil.copy2(args.file, original)
    info = probe(original)
    start = args.start or 0.0
    dur = min(args.duration or 30.0, info["duration"] - start)
    stills = run_dir / "stills"
    stills.mkdir(exist_ok=True)
    sheet = stills / f"sheet-{start:g}-{start + dur:g}.jpg"
    step = max(dur / 12, 0.5)
    run(["ffmpeg", "-y", "-v", "error", "-ss", start, "-t", dur, "-i", original, "-vf",
         f"fps=1/{step:.3f},scale=480:-1,tile=4x3", "-frames:v", "1", sheet])
    cuts = cut_times(original, start, dur)
    print(f"исходник: {original} · {info['width']}×{info['height']} · {info['duration']:.1f} с")
    print(f"лист кадров {start:g}–{start + dur:g} с (кадр каждые {step:.1f} с): {sheet}")
    print("резы в куске (с от начала куска): " + (", ".join(f"{c:g}" for c in cuts) or "нет"))


def cmd_avatar(args) -> None:
    out_dir = WORK / "_avatar" / args.name
    selfies = [as_jpeg(Path(p), out_dir / "src") for p in args.selfie]
    shots = args.only or list(AVATAR_SHOTS)
    if not args.only and not args.force:
        ready = [s for s in shots if (out_dir / f"{s}.png").exists()]
        if ready:
            print(f"уже есть: {', '.join(ready)} в {out_dir} — переиспользую, денег не трачу")
        shots = [s for s in shots if s not in ready]
        if not shots:
            print("аватар готов целиком. Переделать кадр — --only <кадр>, всё заново — --force")
            return
    price = IMAGE_USD_HIGH * len(shots) if args.quality == "high" else 0.1 * len(shots)
    print(f"аватар «{args.name}» → {out_dir}/  ({', '.join(shots)})")
    print(f"модель {IMAGE_MODEL}, качество {args.quality}, селфи: {len(selfies)}")
    print(f"цена ≈ ${price:.2f} (оценка)")
    if plan_only(args):
        return
    key = read_key()
    out_dir.mkdir(parents=True, exist_ok=True)
    for shot in shots:
        size, template = AVATAR_SHOTS[shot]
        refs = list(selfies)
        if shot != "face" and (out_dir / "face.png").exists():
            refs.append(out_dir / "face.png")  # лицо, уже сгенерированное, держит идентичность
        prompt = template.format(outfit=args.outfit)
        if args.build:
            prompt += (f" Body build: {args.build}. Loose clothing in the reference photos hides "
                       "the real figure — do not copy its volume, do not make the person heavier.")
        if args.wardrobe:
            refs.append(Path(args.wardrobe))  # последним: промпт ссылается на «LAST image»
            prompt += WARDROBE_NOTE
        out = out_dir / f"{shot}.png"
        if out.exists():
            out.rename(out_dir / f"{shot}-{stamp()}.png")  # прежние версии не затирать
        res = image_call(prompt, refs, size, args.quality, out, key)
        log({"kind": "avatar", "shot": shot, "model": IMAGE_MODEL, "prompt": prompt,
             "inputs": [str(p) for p in refs], "out": str(out),
             "request_id": res.get("_request_id"), "seconds": res.get("_seconds")})


def cmd_scene(args) -> None:
    out = Path(args.out)
    prompt = args.prompt or SCENE_PROMPT.format(who=args.who)
    print(f"кадр {args.video} @ {args.at} с + {len(args.image)} реф. → {out}")
    print(f"промпт: {prompt}")
    print(f"цена ≈ ${IMAGE_USD_HIGH:.2f} (оценка)")
    if plan_only(args):
        return
    key = read_key()
    out.parent.mkdir(parents=True, exist_ok=True)
    frame = out.with_name(out.stem + "-frame.png")
    run(["ffmpeg", "-y", "-v", "error", "-ss", args.at, "-i", args.video, "-frames:v", "1", frame])
    res = image_call(prompt, [frame] + args.image, "auto", "high", out, key)
    log({"kind": "scene", "model": IMAGE_MODEL, "prompt": prompt, "frame": str(frame),
         "inputs": args.image, "out": str(out), "request_id": res.get("_request_id")})


def cmd_recast(args) -> None:
    kling = args.engine == "kling"
    prompt = with_hands(Path(args.prompt_file).read_text(encoding="utf-8").strip(),
                        not args.no_hands)
    elements = [e.split(",") for e in args.element]
    files = list(args.image) + [p for e in elements for p in e]
    errors = ref_errors(prompt, len(args.image), len(elements))
    errors += [f"нет файла {p}" for p in files if not Path(p).exists()]
    if kling and len(args.image) + len(elements) > KLING_MAX_REFS:
        errors.append(f"персонажей + картинок {len(args.image) + len(elements)}, "
                      f"Kling берёт до {KLING_MAX_REFS}")
    if not kling and elements:
        errors.append("--element только для --engine kling")
    if not kling and len(args.image) > MAX_IMAGES:
        errors.append(f"картинок {len(args.image)}, Seedance берёт до {MAX_IMAGES}")
    duration = args.duration
    if kling and duration is not None and duration > KLING_SAFE_MAX_S:
        print(f"длительность {duration} → {KLING_SAFE_MAX_S} с (предел Kling 15 с после перекодирования)")
        duration = KLING_SAFE_MAX_S
    run_dir = WORK / args.slug
    source = prepare_source(Path(args.video), args.start, duration,
                            run_dir / f"source-{args.start or 0:g}.mp4")
    info = probe(source)
    lo, hi = (KLING_MIN_S, KLING_MAX_S) if kling else (VIDEO_MIN_S, VIDEO_MAX_S)
    if not lo <= info["duration"] <= hi:
        errors.append(f"видео {info['duration']:.2f} с, {args.engine} берёт {lo}–{hi} с "
                      "— режь --start/--duration")
    if kling and min(info["width"], info["height"]) < KLING_MIN_SIDE:
        errors.append(f"сторона видео меньше {KLING_MIN_SIDE} px — Kling не примет")
    print(f"исходник: {source} · {info['width']}×{info['height']} · {info['duration']:.1f} с")
    for i, e in enumerate(elements):
        print(f"@Element {i + 1}: " + ", ".join(Path(p).name for p in e))
    print(f"референсы ({len(args.image)}): " + ", ".join(f"@Image {i + 1}={Path(p).name}"
                                                        for i, p in enumerate(args.image)))
    print("абзац про руки: " + ("есть" if "HANDS ARE THE PRIORITY" in prompt.upper() else "выключен"))
    if kling:
        price = KLING_USD_S * info["duration"]
        print(f"движок: Kling O3 edit, выход в размере исходника, звук: {args.audio}")
        print(f"цена ≈ ${price:.2f} (${KLING_USD_S}/с выхода)")
    else:
        ow, oh = out_dims(args.resolution, info["width"], info["height"])
        price = seedance_usd(info["duration"], info["duration"], ow, oh)
        print(f"движок: Seedance 2.5 editing (реальные лица отклоняет), выход: {ow}×{oh}, "
              f"звук: {args.audio}")
        print(f"цена ≈ ${price:.2f} (оценка: вход + выход по формуле токенов Seedance)")
    for e in errors:
        print(f"  ОШИБКА: {e}")
    if errors:
        sys.exit(1)
    if plan_only(args):
        return
    key = read_key()
    video_url = upload(source, key)
    image_urls = [upload(as_jpeg(Path(p), run_dir / "src"), key) for p in args.image]
    if kling:
        element_urls = [[upload(as_jpeg(Path(p), run_dir / "src"), key) for p in e]
                        for e in elements]
        model = KLING
        payload = kling_payload(prompt, video_url, image_urls, element_urls, args.audio)
    else:
        model = SEEDANCE
        payload = recast_payload(prompt, video_url, image_urls, args.resolution, args.audio,
                                 args.seed)
    res = submit_and_wait(model, payload, key)
    video = res.get("video") or {}
    if not video.get("url"):
        sys.exit(f"в ответе нет video.url: {json.dumps(res)[:600]}")
    out = run_dir / f"recast-{stamp()}-{args.engine}.mp4"
    download(video["url"], out)
    write_meta(out, {"original": str(Path(args.video)), "start": args.start or 0.0,
                     "duration": info["duration"], "engine": args.engine})
    print(f"сохранено: {out}")
    print("дальше: finish --clip <этот файл> [--compare] — звук оригинала и сравнение")
    log({"kind": "recast", "model": model, "slug": args.slug, "prompt_file": args.prompt_file,
         "prompt": prompt, "video": str(source), "images": args.image, "elements": elements,
         "audio": args.audio, "request_id": res.get("_request_id"),
         "seconds": res.get("_seconds"), "price_usd_est": round(price, 2), "out": str(out)})


def cmd_splice(args) -> None:
    base, fix = Path(args.clip), Path(args.fix)
    base_len = probe(base)["duration"]
    plan = splice_plan(args.at, args.to, base_len)
    parts, labels = [], []
    for i, (src, a, b) in enumerate(plan):
        idx = 0 if src == "base" else 1
        parts.append(f"[{idx}:v]trim={a}:{b},setpts=PTS-STARTPTS,fps=24,format=yuv420p[p{i}]")
        labels.append(f"[p{i}]")
    graph = ";".join(parts) + ";" + "".join(labels) + f"concat=n={len(plan)}:v=1:a=0[v]"
    out = base.with_name(f"{base.stem.split('-splice')[0]}-splice-{stamp()}.mp4")
    run(["ffmpeg", "-y", "-v", "error", "-i", base, "-i", fix, "-filter_complex", graph,
         "-map", "[v]", "-c:v", "libx264", "-crf", "16", "-preset", "slow", out])
    if meta_path(base).exists():
        write_meta(out, read_meta(base))
    print("склейка: " + " + ".join(f"{s} {a:g}–{b:g}" for s, a, b in plan))
    print(f"сохранено: {out}")
    print("дальше: finish --clip <этот файл> [--compare]")


def cmd_finish(args) -> None:
    clip = Path(args.clip)
    if args.original:
        meta = {"original": args.original, "start": args.start or 0.0, "duration": args.duration}
    else:
        meta = read_meta(clip)
    dur = meta["duration"] or probe(clip)["duration"]
    orig = Path(meta["original"])
    out_dir = clip.parent
    tag = stamp()
    final = out_dir / f"final-{tag}.mp4"
    run(["ffmpeg", "-y", "-v", "error", "-i", clip, "-ss", meta["start"], "-t", dur, "-i", orig,
         "-map", "0:v", "-map", "1:a?", "-vf", f"fps={IPHONE_FPS}", *IPHONE_ARGS, "-shortest",
         final])
    print(f"клип со звуком оригинала: {final}")
    if args.compare:
        cmp_ = out_dir / f"compare-{tag}.mp4"
        info = probe(clip)
        stack = "vstack" if info["width"] >= info["height"] else "hstack"
        w = 960 if stack == "vstack" else -2
        h = -2 if stack == "vstack" else 960
        run(["ffmpeg", "-y", "-v", "error", "-ss", meta["start"], "-t", dur, "-i", orig, "-i", final,
             "-filter_complex",
             f"[0:v]fps={IPHONE_FPS},scale={w}:{h},setsar=1[a];"
             f"[1:v]fps={IPHONE_FPS},scale={w}:{h},setsar=1[b];[a][b]{stack}[v]",
             "-map", "[v]", "-map", "1:a?", *IPHONE_ARGS, "-shortest", cmp_])
        where = "сверху оригинал, снизу результат" if stack == "vstack" else "слева оригинал, справа результат"
        print(f"сравнение ({where}): {cmp_}")


def cmd_iphone(args) -> None:
    for src in args.files:
        src = Path(src)
        out = src.with_name(src.stem + "-iphone.mp4")
        run(["ffmpeg", "-y", "-v", "error", "-i", src, "-vf", f"fps={IPHONE_FPS},setsar=1",
             *IPHONE_ARGS, out])
        print(f"для айфона: {out}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    sub = ap.add_subparsers(dest="cmd", required=True)

    ck = sub.add_parser("check", help="окружение и ключ")
    ck.set_defaults(fn=cmd_check)

    st = sub.add_parser("status", help="что уже сделано и можно переиспользовать")
    st.set_defaults(fn=cmd_status)

    fe = sub.add_parser("fetch", help="скачать/взять исходник, лист кадров, резы")
    src = fe.add_mutually_exclusive_group(required=True)
    src.add_argument("--url")
    src.add_argument("--file")
    fe.add_argument("--slug", required=True)
    fe.add_argument("--start", type=float, help="начало куска для листа кадров, с")
    fe.add_argument("--duration", type=float, help="длина куска для листа кадров, с")
    fe.set_defaults(fn=cmd_fetch)

    av = sub.add_parser("avatar", help="референсы персонажа из селфи")
    av.add_argument("--selfie", action="append", required=True, help="сырые фото человека (лицо, фигура), 1–4 штуки, HEIC можно")
    av.add_argument("--name", default="me")
    av.add_argument("--outfit", default="the same outfit as in the reference photos")
    av.add_argument("--build", help="телосложение словами: вес, фигура — свободная одежда на селфи врёт")
    av.add_argument("--wardrobe", help="референс стиля одежды: с фото берётся только одежда и украшения, не лицо")
    av.add_argument("--only", action="append", choices=list(AVATAR_SHOTS), help="переснять один кадр")
    av.add_argument("--force", action="store_true", help="переснять все кадры, даже готовые")
    av.add_argument("--quality", default="high", choices=["low", "medium", "high"])
    av.add_argument("--yes", action="store_true")
    av.set_defaults(fn=cmd_avatar)

    sc = sub.add_parser("scene", help="кадр исходника с персонажем вместо исполнителя")
    sc.add_argument("--video", required=True)
    sc.add_argument("--at", type=float, default=1.0, help="секунда кадра")
    sc.add_argument("--image", action="append", required=True, help="референс персонажа")
    sc.add_argument("--who", default="the main performer", help="кого заменить, по-английски")
    sc.add_argument("--prompt", help="свой промпт вместо шаблона")
    sc.add_argument("--out", required=True)
    sc.add_argument("--yes", action="store_true")
    sc.set_defaults(fn=cmd_scene)

    rc = sub.add_parser("recast", help="перекаст куска видео")
    rc.add_argument("--video", required=True)
    rc.add_argument("--engine", default="kling", choices=["kling", "seedance"],
                    help="kling — по умолчанию: Seedance на fal отклоняет фото реальных людей")
    rc.add_argument("--element", action="append", default=[],
                    help="Kling: персонаж @Element N — 'лицо.png,рост.png,лист.png', первым лицо")
    rc.add_argument("--image", action="append", default=[], help="@Image N — в порядке флагов")
    rc.add_argument("--prompt-file", required=True)
    rc.add_argument("--no-hands", action="store_true", help="не дописывать абзац про руки")
    rc.add_argument("--slug", required=True, help="папка результатов")
    rc.add_argument("--start", type=float, help="кусок: начало, с")
    rc.add_argument("--duration", type=float, help="кусок: длина, с")
    rc.add_argument("--resolution", default="720p", choices=["480p", "720p", "1080p"],
                    help="только Seedance; Kling отдаёт в размере исходника")
    rc.add_argument("--audio", default="original", choices=["original", "generated", "none"])
    rc.add_argument("--seed", type=int)
    rc.add_argument("--yes", action="store_true")
    rc.set_defaults(fn=cmd_recast)

    sp = sub.add_parser("splice", help="вклеить исправленный кусок в клип")
    sp.add_argument("--clip", required=True, help="клип, в который вклеиваем")
    sp.add_argument("--fix", required=True, help="исправленный кусок, начинается с --at")
    sp.add_argument("--at", type=float, default=0.0, help="с какой секунды клипа заменить")
    sp.add_argument("--to", type=float, required=True, help="до какой секунды — лучше по резу")
    sp.set_defaults(fn=cmd_splice)

    fi = sub.add_parser("finish", help="звук оригинала и сравнение")
    fi.add_argument("--clip", required=True)
    fi.add_argument("--compare", action="store_true", help="ещё и видео-сравнение")
    fi.add_argument("--original", help="если у клипа нет .json: исходное видео")
    fi.add_argument("--start", type=float)
    fi.add_argument("--duration", type=float)
    fi.set_defaults(fn=cmd_finish)

    ip = sub.add_parser("iphone", help="пережать готовые файлы так, чтобы их брала галерея айфона")
    ip.add_argument("files", nargs="+")
    ip.set_defaults(fn=cmd_iphone)

    args = ap.parse_args()
    args.fn(args)


if __name__ == "__main__":
    main()
