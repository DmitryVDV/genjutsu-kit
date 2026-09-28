# Промпт перекаста для Kling O3 edit — два персонажа

Скопировать в `<результаты>/<slug>/prompt.txt` и подставить переменные. `@Element1` и `@Element2` — персонажи в порядке флагов `--element`, `@Video1` — исходник. Абзац про руки скрипт допишет сам; он приведён в конце для справки.

Готовых значений в шаблоне нет: каждую переменную уточни у человека. Пока в промпте осталась хоть одна `{ПЕРЕМЕННАЯ}`, `recast` не запустится.

## Промпт

```
Edit @Video1. Replace the viewer's LEFT performer ({LEFT_MARK}) with @Element1: {OUTFIT_1}. Replace the viewer's RIGHT performer ({RIGHT_MARK}) with @Element2: {OUTFIT_2}. {IDENTITY} Each outfit stays on its own performer for the whole video.
Keep the original framing of every shot exactly: wide shots stay wide, close shots stay close — do not zoom in.
Keep all motion, expressions, lip movement, timing, camera cuts, lighting, background and props from @Video1. Do not swap positions or invent new movement.
```

## Переменные и откуда их брать

Все значения — по-английски.

| Переменная | Что это | Откуда |
|---|---|---|
| `{LEFT_MARK}`, `{RIGHT_MARK}` | чем исполнители различаются в исходнике, чтобы модель не перепутала, кого на кого менять | Claude смотрит лист кадров (шаг 2) и предлагает, человек подтверждает |
| `{OUTFIT_1}`, `{OUTFIT_2}` | образ слева и образ справа | человек пишет словами, **или** из фото-референса: Claude описывает одежду и украшения с фото, человек подтверждает и дополняет то, чего не видно (низ, обувь). Те же слова, что в `--outfit` у аватара |
| `{IDENTITY}` | кто персонажи и их внешность; что убрать у исполнителей (дреды, тёмные очки) | один человек или двое — ответ из шага 3; внешность — по сырым фото, убрать — по листу кадров; Claude предлагает, человек подтверждает |

### Две формы `{IDENTITY}`

Один человек в двух образах:
```
@Element1 and @Element2 are the same <man/woman> in two outfits: same face, <glasses, haircut, beard>. Remove from both performers: <dreadlocks, sunglasses>.
```

Два разных человека:
```
@Element1 and @Element2 are two different people: keep each face exactly as in its own references, never blend them. @Element1: <man/woman, glasses, haircut>. @Element2: <man/woman, glasses, haircut>. Remove from both performers: <dreadlocks, sunglasses>.
```

## Абзац про руки (дописывается автоматически, `--no-hands` выключает)

```
HANDS ARE THE PRIORITY. Copy every hand and finger pose from @Video1 exactly: the same finger positions, the same crossed and interlocked fingers, the same contact points and the same timing. Each hand has exactly five fingers. When a hand comes up to the face it stays in front of the face and touches the mouth or chin exactly as in @Video1 — a hand never passes through the head or the face. No distorted, merged, bent-backwards or extra fingers.
```
