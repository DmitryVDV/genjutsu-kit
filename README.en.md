[Русский](README.md) · **English**

# Genjutsu via fal.ai — a ready-made Claude Code project

Redo someone else's video or a trend with you instead of the performers: the motion, facial expressions, timing and camera come from the video, the face and body come from your photos. Left and right — you in two looks, or two different people. You get two files, the clip and an "original above result" comparison, both ready for the iPhone gallery.

<a href="https://www.youtube.com/shorts/CoiIKzihwpU"><img src="https://i.ytimg.com/vi/CoiIKzihwpU/oar2.jpg" width="260" alt="Example on YouTube"></a>

A 15-second clip costs about $5–6 on fal.ai. Claude guides you step by step, asks one question at a time and tells you the price before every spend.

**[Detailed guide with pictures →](https://dmitryvdv.github.io/genjutsu-kit/en/)**

---

## Run it in Claude Desktop — no terminal

You need a Mac, the [Claude Desktop](https://claude.ai/download) app and a Pro, Max, Team or Enterprise subscription.

### First time

**1. Switch to Code.** Top left, next to the arrows, there are two icons: the speech bubble is Chat, `</>` is Code. Click `</>`.

<img src="docs/desktop/desktop-1-code-tab.png" width="420" alt="Chat / Code switch">

**2. Choose a folder.** Click **+ New**. Above the input box there are two buttons: make sure the first one says **Local**. Click the second one — **No folder** → **Open folder…**. In the dialog, create an empty folder with the "New Folder" button, for example `Documents/Genjutsu`, and click "Open".

<img src="docs/desktop/desktop-2-folder.png" width="420" alt="Local and No folder buttons">

**3. Paste this text into the chat and send it.** The copy button is in the top right corner of the block.

```text
Install the project from this link: https://github.com/DmitryVDV/genjutsu-kit

1. Download all files straight into this folder, not into a subfolder. If git is missing, download the archive from GitHub and unpack it here.
2. Check that python3, ffmpeg and yt-dlp are installed. Install what's missing, or explain in simple words what I should do.
3. Create a .env file from .env.example and open it in TextEdit so I can paste my fal.ai key. Don't ask for the key in the chat.
4. When I write "done", read .claude/skills/genjutsu/SKILL.md and guide me through it from step 0, one question at a time. Talk to me in English.
```

<!-- screenshot: docs/desktop/desktop-3-install.png -->

**4. Paste your key.** Claude opens the `.env` file in TextEdit. Paste your fal.ai key right after `FAL_KEY=`, save (`Cmd+S`) and write "done" in the chat. Get the key at [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys); a $10 balance covers 1–2 clips.

<!-- screenshot: docs/desktop/desktop-5-key.png -->

**5. Allow commands.** Claude asks permission before every command — click "allow". Money is spent only after you say "yes" in the chat.

<!-- screenshot: docs/desktop/desktop-4-permission.png -->

**6. Photos — drag them into the chat.** When Claude asks for photos, drag them into the input box and label them: "raw photos — this is me", "style reference for the left look".

<!-- screenshot: docs/desktop/desktop-6-attach.png -->

### What Claude asks next

Video and seconds → you in two looks or two different people → raw photos, height and weight → outfit style for the left and right look (in words or a style reference photo) → who goes where and the Reels format → 6-second test run → the full segment → fixes.

Not sure which video to use? Start with the tested one: Quavo & Takeoff — Hotel Lobby (A COLORS SHOW), https://www.youtube.com/watch?v=x9yop0nYR9g, seconds 0:12–0:27.

### Next time

Code tab → **+ New** → **Local** → the folder button → **Open folder…** → your `Genjutsu` folder. Write in plain words "I want to redo a trend" or the `/genjutsu` command.

The command appears only in a new chat after installation: in the chat where you installed it, it isn't there yet, and that's fine.

<!-- screenshot: docs/desktop/desktop-9-skill.png -->

### If something goes wrong

| What happened | What to do |
|---|---|
| Claude doesn't understand what you mean | Write: "read .claude/skills/genjutsu/SKILL.md and guide me through it". If it can't see the file, the wrong folder is selected: start a new chat and pick the `Genjutsu` folder. |
| Chat mode is open (speech-bubble icon) | It won't work: code runs in the cloud there, without your folder, key and ffmpeg. Use Code with Local only. |
| It says "ffmpeg: НЕТ" (not found) although it's installed | Quit Claude completely (`Cmd+Q`) and open it again. If that doesn't help, open the Local environment settings (the gear by the input box) and add `/opt/homebrew/bin` to `PATH`. |
| Generation takes a long time | A video takes 5–16 minutes in the background. Don't close the app and don't let the Mac sleep. Progress is under Views → Tasks. |
| The key ended up in the chat by accident | Delete it at [fal.ai/dashboard/keys](https://fal.ai/dashboard/keys), create a new one and put it in `.env`. |

---

## Prices (September 2026)

| What | Price |
|---|---|
| A look (portfolio: face, full body, four-side view) | ≈ $0.9 |
| Redo one image of a look | ≈ $0.3 |
| 6-second test run | ≈ $1 |
| Full 15-second segment | ≈ $2.5 |
| Fix a 3-second segment | ≈ $0.5 |
| **Whole 15-second clip** | **≈ $5–6** |

Photos and looks are uploaded to fal storage under a link nobody can guess. If the source video has someone else's music, Instagram may mute the sound.

---

## For terminal users

```bash
git clone https://github.com/DmitryVDV/genjutsu-kit genjutsu-kit && cd genjutsu-kit
brew install ffmpeg yt-dlp          # Python 3.9+ ships with macOS
cp .env.example .env                # paste your key after FAL_KEY=
claude                              # then type /genjutsu
```

To use it in another project, copy the `.claude/skills/genjutsu` folder (and `tools/` if you like).

The skill's instructions for Claude are written in Russian; Claude still talks to you in your language.

### What's inside

| Path | What it is |
|---|---|
| `.claude/skills/genjutsu/SKILL.md` | instructions for Claude: steps, questions, what to reuse |
| `.claude/skills/genjutsu/scripts/genjutsu.py` | the whole pipeline: `check`, `status`, `fetch`, `avatar`, `scene`, `recast`, `splice`, `finish`, `iphone` |
| `.claude/skills/genjutsu/templates/recast-prompt.md` | two-character prompt with variables and the hands paragraph |
| `tools/to-iphone.sh` | re-encode any video so the iPhone gallery accepts it |
| `tools/compare.sh` | "original above result" comparison |
| `tools/add-audio.sh` | put the original sound onto the result |
| `tools/contact-sheet.sh` | 4×3 contact sheet and cut timestamps |
| `tools/download.sh` | download a video from YouTube / Instagram (yt-dlp) |
| `tools/photo-prep.sh` | HEIC → JPEG and a close face crop |
| `index.html`, `en/index.html` | detailed guide for people (Russian, English), served via GitHub Pages |
| `docs/desktop/` | Claude Desktop screenshots for the guides |
