# Holocron

A terminal companion for monitoring shifts. Your error board, notes, reminders, meetings and shift hours in one window. Nothing renders, nothing runs in the background, no GPU drain.

I kept every error I ran into at work on one Excalidraw board: the message, the cause, the fix. On monitoring shifts I need it at hand all the time, so it stayed open in Obsidian. A board that size keeps the GPU busy and noticeably drains a laptop's battery. Its search also only found the exact wording, so if I didn't remember how I'd phrased something, I didn't find it.

Holocron reads the same file from the terminal and gets me the right block in a second. Over time the reminders, meetings and shift hours I kept checking in other apps moved here too, so one terminal window now covers the whole shift.

So drop everything on a board and don't worry about order or wording. Skip a word, use a different word form or make a typo, and the right block still comes up, ready to read or edit.

<img width="2388" height="2022" alt="CleanShot 2026-10-10 kpVgcpSX@2x" src="https://github.com/user-attachments/assets/11a8a3c2-0327-4de3-89ff-41bdb1dbcd33" />

## What's inside

- **Search everything.** Every text block on a drawing and every card on a kanban board is its own result, alongside your regular Markdown notes.
- **Several searches at once.** Type `nginx; ERR504` and each part gets its own group of results.
- **Edit in place.** Fix text on a drawing, open a note in your editor, tick off a task with `x 3` or write a new note with `note`. Changes go straight to the file.
- **Jump between records.** `[[Links]]` work in notes and board blocks alike. A link finds a block by its first line or a note by its name, and `j 2` takes you there.
- **Ask your notes.** Keeper answers questions by quoting your notes. The model runs on your computer or your own server, so your notes stay private.
- **Know your hours.** A regular 9 to 5 or a rotating cycle of up to 52 weeks, with night shifts, vacations and time zones.
- **See what's coming.** The next reminders and calendar events are on the main screen, with meeting links pulled out of the invite.
- **Remind by place.** Waypoints tie reminders to an address, so they fire when you arrive or leave (macOS only).
- **Pin what you use.** Favorites open with a single key.

## Search that forgives

You don't need to remember how you wrote something. Holocron catches:

- typos, one or two letters off depending on word length
- other word forms, so `timeout`, `timeouts` and `timed out` find each other (works for Russian endings too)
- missing words: a long query still matches if most of it is there
- `ё` and `е`, hyphens and underscores, all treated the same

Codes and short words are matched exactly, so `ERR504` won't turn up `ERR503`. Hits in a block's title rank higher, and an exact phrase goes to the top. If nothing matches, Holocron suggests a corrected query from words that are actually in your archive.

To look for several things at once, put `;` between them: `nginx; ERR504`. Each part is searched on its own and gets its own group, and every group starts on the first page. A record that matches more than one part shows up once. If `;` gets in the way of what you paste, change the symbol or turn it off in settings (`s` > Archive > Search separator).

## Excalidraw from the terminal

Works with drawings from the Excalidraw plugin for Obsidian, compressed or not, and with plain `.excalidraw` files or a whole folder of them.

- **One block, one result.** A board with 40 sticky notes gives you 40 things to find, not one file to dig through.
- **Sorted by name.** Blocks of a board are listed by their first line, the same way as in `l`. Browse a board with `tree`.
- **Edit without opening the drawing.** Press `e`, change the text and save. The drawing itself is updated, so Excalidraw shows the change next time. If the block changed on disk while you were editing, for example through iCloud, nothing is overwritten and your text goes to the clipboard, so you can paste it again.
- **Links between blocks.** Write `[[Block title]]` in any block to link to another one. Holocron looks on the same board first, then for a note with that name, then on other boards. If the title changed or several blocks fit, `j` opens a search instead of a dead end.

## Notes and vault

Point Holocron to an Obsidian vault and every Markdown note becomes searchable next to the boards. Folders you don't need can be excluded in settings, where you also see how many notes each folder holds.

- `[[Wikilinks]]` in a note get numbers. Type `j 2` to jump to the second one and `b` to come back.
- Checkboxes like `- [ ]` can be ticked with `x 3` without leaving the note.
- `note` opens your editor and saves a new note to the folder you chose. The first line becomes the file name, and the name follows it when you change the first line later. If other records link to the note, the name stays, so no link breaks. Clear a note's text in the editor to move it to the trash. Holocron asks first and warns if other records link to it.
- `tree` browses the archive by folder and opens kanban boards list by list.
- `f` pins the open record to favorites, or the board you're browsing in `tree`.

## Kanban boards

Boards made with the Kanban plugin for Obsidian are read as boards, not as plain notes.

- **One card, one result.** Search finds each card on its own and the board itself by its name. Cards in a done list are shown like any other, nothing is hidden or dimmed, so a board you keep as a record with notes on each card works as well as a to-do list.
- **Lists in `tree`.** A board opens as its lists, in the same order as in Obsidian, empty ones included. Cards keep their order within a list. If you open a board from search or `l`, `n` and `p` move on to the neighbouring records once the board's pages run out.
- **Add, edit, move.** `a` adds a card to the open list or to the list of the open card, `e` edits a card and `m` moves it to another list. A card moved into a done list gets ticked, and one moved out gets unticked. Changes go straight to the file. If the card changed on disk in the meantime, nothing is overwritten.
- **Pin a board.** Press `f` on a board in `tree` to open it from favorites.

## Keeper

Keeper is a local assistant for your archive. Ask in your own words, in any language, and it answers from your records: it refers to them by number, shows the exact lines it relied on and lists the links from those records (an instruction, a ticket, a doc). It keeps track of the conversation, so "what about the second one?" works.

Press `k` on an open record to ask about that record only. Paste an error there and Keeper gives the steps from the record. If the error compares two amounts, Holocron works out the difference itself and shows the calculation above the steps, so the numbers don't depend on the model. Errors the record says can come up after the fix are listed under What may follow. Ask for a command or a query from the record with your own values, and Keeper copies it from the record with only those values changed. Codes and numbers in it that you didn't type are listed under it, so you know what to check before running it. The model can still get a command wrong, so read it before you run it. If the record doesn't cover your question, type `/` to ask the whole archive.

Keeper runs on [Ollama](https://ollama.com/download). Settings show what's missing, and if you don't have a model yet, they can download the recommended `qwen2.5:7b` for you. You can also add the address of another machine running Ollama. Keeper uses that server when it's reachable and switches to your own computer when it's not.

## Shifts

Describe your schedule once in settings (`s` > Schedule):

- **Weeks.** One week for a fixed schedule, or a cycle of up to 52 weeks for rotating shifts. Hours are typed as `7-15` or `20-7` for a night shift, and several days can be set at once with `1-5`.
- **Current week.** Tell Holocron where in the cycle you are today and it works out the rest.
- **Vacations.** Days off in the cycle are skipped and the next shift is counted after them.
- **Time zone and clocks.** Keep shift hours in your team's time zone and add clocks for other cities.
- **Share.** Holocron turns your schedule into a short code and copies it. A colleague pastes it into Import and gets the same cycle. Their vacations stay as they are.

The main screen tells you if you're on shift and when the next one starts. `schedule` shows it week by week: `n` and `p` to move, `+4` to jump ahead, `t` for this week, or type a date like `14-11`.

## Reminders and calendar (macOS)

Holocron works with Apple Reminders through [remindctl](https://github.com/openclaw/remindctl) and with Apple Calendar through [ekctl](https://github.com/schappim/ekctl). You don't have to set them up yourself. Open settings (`s`), pick Reminders or Calendar, and Holocron walks you through it: it checks your macOS version, downloads the tool with one key (or installs it with Homebrew, if you prefer), asks macOS for access and, if that doesn't work, opens the right page in System Settings.

Then choose which lists and calendars to show, which one is the default, how many items the main screen shows and how many days ahead to look.

Settings also show which copy of the tool Holocron uses, the one it downloaded or the one from Homebrew. Press `i` to see where it is and delete it.

- **Reminders.** View, tick off (`x 2`) and edit reminders. Add one with `a`: `Call the vendor #work @office`. `#list` and `@waypoint` are optional.
- **Waypoints.** Save an address under a short name like `office` once, then use `@office` in any reminder. Choose whether it fires on arrival or when you leave, and set the radius (100 m by default).
- **Calendar.** Upcoming events grouped by day. Add one with `a`: `Standup 10:00` or `Lunch tomorrow 12:30-13:30 #work`.
- **Meeting links.** Holocron looks for links in the event URL, location, notes and invitees and shows the meeting link right under the event: Zoom, Google Meet, Teams, Webex, Whereby, Jitsi and Telemost.

On Windows and Linux everything else works the same, only reminders and calendar are macOS-only. If you need them on another system, [open an issue](https://github.com/Gustxxl/holocron/issues).

## Commands

Type `h` in Holocron for the full list. The main ones:

| Command             | What it does                                         |
| ------------------- | ---------------------------------------------------- |
| any words           | search the archive                                   |
| `words; more words` | several searches at once                             |
| `l`                 | browse all records                                   |
| `k`, `keeper`       | ask Keeper                                           |
| `sch`, `schedule`   | shift schedule                                       |
| `c`, `calendar`     | Apple Calendar events                                |
| `r`, `reminders`    | Apple Reminders                                      |
| `wp`, `waypoints`   | places for location reminders                        |
| `f`, `favorites`    | pinned records                                       |
| `tree`              | browse by folder and board                           |
| `note`              | write a new note                                     |
| `s`, `settings`     | name, archive, schedule, Keeper, reminders, calendar |
| `check`             | run diagnostics and tests                            |
| `update`            | install a pending update                             |
| `nn` / `pp`         | last / first page or record                          |
| `b` / `w` / `q`     | back / main screen / quit                            |

## Get started

You need [Python 3.12+](https://www.python.org/downloads/) on macOS 14+, Windows 10+ or Linux. [Ollama](https://ollama.com/download) is optional, for Keeper.

```zsh
git clone https://github.com/Gustxxl/holocron.git
cd holocron
python3 install.py
```

No Git? Download the ZIP (Code > Download ZIP), unzip it and run `python3 install.py` inside the folder.

Open a new terminal and run:

```zsh
holo
```

On first launch Holocron creates its own virtual environment and installs what it needs, so your system Python stays clean. Point it to your board, vault or drawings in settings (`s`).

Words after `holo` go straight to search: `holo nginx timeout` opens the results, and `b` takes you to the main screen. Commands work the same way: `holo schedule`, `holo update`. Put several searches in quotes, since the shell splits on `;`: `holo "nginx; ERR504"`. To search for something that starts with a dash, put `--` first: `holo -- -bash: command not found`. That makes `holo` easy to use from aliases and scripts. `holo --help` lists all of this.

## Updates

Holocron checks for a new version in the background on launch, and the main screen tells you when there is one. Type `update` to install it. Every downloaded file is checked against GitHub's hashes before anything is replaced. If something goes wrong halfway, the previous version is restored. Your settings and data stay untouched.

If downloads from GitHub are slow or blocked on your network, the update archive comes through mirrors. The version check and the file hashes always come from api.github.com, so a mirror can't change what gets installed, and updates need api.github.com to be reachable. You can set your own mirrors with the `HOLOCRON_MIRROR` environment variable, separated by commas.

## Small things

- `check` runs the built-in tests and shows what's connected: editor, clipboard, reminders, calendar, Keeper and the size of your archive.
- `s` > Lists sets how many rows `l`, `tree` and boards show per page: from 5 to 99, 15 by default.
- Text pasted into search or Keeper keeps its line breaks, so an error window looks the same as where you copied it from.
- A line of `---`, `***` or `___` after a blank line is drawn across the whole window, as in Obsidian. Lines like that right under text, or the matching lines around a pasted error window, keep their own length.
- On a MacBook, the trackpad gives a light tap when you toggle something and a different pattern for success or error.
- `hyperspace`. Try it. Any key brings you back.

## Remove

```zsh
python3 install.py --remove
```

This removes the `holo` command and the reminders and calendar tools Holocron downloaded. Tools installed with Homebrew stay, Holocron prints the command to remove them. Then delete the Holocron folder.

---

Holocron is an independent, unofficial project inspired by the Star Wars universe.
It is not affiliated with or endorsed by Lucasfilm Ltd. or Disney.
