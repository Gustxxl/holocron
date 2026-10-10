# Holocron

Search and edit the text on your Excalidraw boards — and the rest of your notes — from the terminal.

Excalidraw boards fill up with labels, boxes and sticky notes, and there's no quick way to get to that text without opening the drawing. Holocron reads it straight from the files: every word on every board is searchable and editable in a second, without launching Obsidian or Excalidraw.

- **Search everything** — every text block on a board is its own result, alongside your regular notes. Type a few words, typos are fine.
- **Edit in place** — fix text on a drawing, open a note in your editor or tick off a task with `x 3`. Changes go straight to the file.
- **Ask your notes** — Keeper answers questions by quoting the notes themselves. The model runs on your computer or your own server, so your notes stay private.
- **Know your hours** — a regular 9–5 or a rotating shift cycle. See if you're on the clock and what's next.
- **Pin what you use** — favorites open with a single key.

<img width="2388" height="2022" alt="CleanShot 2026-10-10 kpVgcpSX@2x" src="https://github.com/user-attachments/assets/11a8a3c2-0327-4de3-89ff-41bdb1dbcd33" />

## Excalidraw, from the terminal

Works with drawings from the Excalidraw plugin for Obsidian, compressed or not, and with plain `.excalidraw` files.

- **One block, one result.** A board with 40 sticky notes gives you 40 things to find, not one file to dig through.
- **Reads like a page.** Blocks are listed top to bottom, left to right — browse a whole board with `l`.
- **Edit without opening the drawing.** Press `e`, change the text, confirm with `y`. The drawing itself is updated, so Excalidraw shows the change next time.

## Get started

You need [Python 3.12+](https://www.python.org/downloads/) on macOS 14+, Windows 10+ or Linux. [Ollama](https://ollama.com/download) is optional, for Keeper. Everything else installs on first launch.

```zsh
git clone https://github.com/Gustxxl/holocron.git
cd holocron
python3 install.py
```

No Git? Download the ZIP (Code → Download ZIP), unzip it and run `python3 install.py` inside the folder.

Open a new terminal and run:

```zsh
holo
```

Point Holocron to your vault or drawings in settings (`s`). Type `h` for all commands.

## Update and remove

Holocron checks for updates on launch — type `update` to install. To remove the command:

```zsh
python3 install.py --remove
```

Then delete the Holocron folder.

---

Holocron is an independent, unofficial project inspired by the Star Wars universe.
It is not affiliated with or endorsed by Lucasfilm Ltd. or Disney.
