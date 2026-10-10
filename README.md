<img width="2376" height="2006" alt="CleanShot 2026-10-10 h0GElfdF@2x" src="https://github.com/user-attachments/assets/0da9649f-84c6-41f4-9540-b1919040bbba" /># Holocron

Your Obsidian notes, one command away.

Holocron opens in the terminal in a second and finds what you need without launching Obsidian.
It works with your vault folder directly — nothing to import, nothing to sync.

- **Find anything** — type a few words, typos are fine. Text inside Excalidraw drawings is searched too.
- **Ask your notes** — Keeper answers questions by quoting the notes themselves. The model runs on your computer or your own server, so your notes stay private.
- **Edit in place** — open a note in your editor or tick off a task with `x 3`. Changes go straight to the file.
- **Know your hours** — a regular 9–5 or a rotating shift cycle. See if you're on the clock and what's next.
- **Pin what you use** — favorites open with a single key.

<img width="2376" height="2006" alt="CleanShot 2026-10-10 h0GElfdF@2x" src="https://github.com/user-attachments/assets/60092f5c-649a-43e3-a643-e9ebd16b9d8e" />


## Get started

You need [Python 3.12+](https://www.python.org/downloads/) on macOS 14+, Windows 10+ or Linux.
[Ollama](https://ollama.com/download) is optional, for Keeper. Everything else installs on first launch.

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

Point Holocron to your vault in settings (`s`). Type `h` for all commands.

## Update and remove

Holocron checks for updates on launch — type `update` to install. To remove the command:

```zsh
python3 install.py --remove
```

Then delete the Holocron folder.

---

Holocron is an independent, unofficial project inspired by the Star Wars universe.
It is not affiliated with or endorsed by Lucasfilm Ltd. or Disney.
