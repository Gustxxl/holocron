import re
import difflib
from core import archives, search
from ui.interface import clear_screen, dim, pause, read_command, error_haptic, open_file
import textwrap
from screens.help_screen import render_help
from core.commands import HELP_SECTIONS
import shutil
from core.editor import edit_text
from core import excalidraw


_HL = "\033[1;38;2;116;167;254m"
_RESET = "\033[0m"


_URL_RE = re.compile(r'https?://\S+')


def highlight_links(text):
    return _URL_RE.sub(lambda m: dim(m.group()), text)


def _hl_match(qw, tw):
    if qw in tw:
        return True
    if len(qw) <= 3:
        return False
    if tw.startswith(qw) or qw.startswith(tw):
        return True
    if abs(len(tw) - len(qw)) > 3:
        return False
    return difflib.SequenceMatcher(None, qw, tw).ratio() >= search.MATCH_MIN


def highlight(text, query):
    terms = search._norm_words(query)
    if not terms:
        return text

    def repl(m):
        word = m.group(0)
        if any(_hl_match(t, word.lower()) for t in terms):
            return f"{_HL}{word}{_RESET}"
        return word

    return re.sub(r"\w+", repl, text, flags=re.UNICODE)


PAGE = 8
MIN_QUERY = 3


def search_screen(initial_query=None):
    cases = archives.cases()
    if not cases:
        clear_screen()
        print("No excalidraw scenes found.")
        pause()
        return

    query = (initial_query or "").strip()
    if 0 < len(query) < MIN_QUERY:
        clear_screen()
        print(f'Type at least {MIN_QUERY} characters.')
        pause()
        return
    results = search.search(cases, query) if query else []
    page = 0

    while True:
        if query and not results:
            clear_screen()
            print(f'Nothing found for "{query}".')
            tips = search.suggest(cases, query)
            if tips:
                print(dim("Maybe: " + ", ".join(tips)))
            print()
            print(dim('  [type] search   [b] back   [h] help'))
            print()
            error_haptic()
        elif results:
            page = show_list(results, page, query)
        else:
            clear_screen()
            print(dim('Search the archive'))
            print()
            print(dim('  [type] search   [b] back'))
            print()

        command = read_command('search> ')
        low = command.lower()
        if low in ('h', 'help'):
            clear_screen()
            render_help(HELP_SECTIONS)
            pause()
            continue
        if low in ('s', 'settings'):
            from screens.settings_screen import settings_screen
            settings_screen()
            archives.load()
            cases = archives.cases()
            if query:
                results = search.search(cases, query)
            continue
        if low in ('b', 'back'):
            return
        if command == '':
            if not results:
                return
            archives.load()
            cases = archives.cases()
            if query:
                results = search.search(cases, query)
            continue
        if low == 'n' and results:
            page += 1
            continue
        if low == 'p' and results:
            page -= 1
            continue
        if command.isdigit() and results:
            open_case(results, int(command), query)
            continue

        q = command.strip()
        if len(q) < MIN_QUERY:
            clear_screen()
            print(f'Type at least {MIN_QUERY} characters.')
            pause()
            continue

        query = q
        results = search.search(cases, query)
        page = 0


def open_case(results, number, query):
    while 1 <= number <= len(results):
        show_case(results[number - 1][1], query)
        command = read_command('case> ')
        low = command.lower()

        if low in ('e', 'edit'):
            case = results[number - 1][1]
            fp = case.get("filepath")
            eid = case.get("element_id")

            if not fp or not eid:
                print(dim("  Editing not available for this case"))
                pause()
                continue

            if not fp.endswith('.excalidraw'):
                print(dim("  Editing supported only for .excalidraw files"))
                pause()
                continue

            original = case["text"]
            edited = edit_text(original).strip()

            if not edited:
                print(dim("  Empty text — edit cancelled"))
                pause()
                continue

            if edited == original:
                print(dim("  No changes"))
                pause()
                continue

            clear_screen()
            print(dim("  Old:"))
            print(f"  {original[:200]}")
            print()
            print(dim("  New:"))
            print(f"  {edited[:200]}")
            print()
            confirm = read_command("  Save changes? [y/n]> ")
            if confirm.lower() != 'y':
                print(dim("  Cancelled"))
                pause()
                continue

            try:
                excalidraw.update_text(fp, eid, edited)
                case["text"] = edited
                print(dim("  Saved"))
            except Exception as e:
                print(f"  Error: {e}")
            pause()
            continue

        if low in ('h', 'help'):
            clear_screen()
            render_help(HELP_SECTIONS)
            pause()
            continue
        if low in ('b', 'back'):
            return
        if command == '':
            archive_mod = __import__('core.archives', fromlist=['archives'])
            archive_mod.load()
            if query:
                results = search.search(archive_mod.cases(), query)
            continue
        if command.isdigit():
            number = int(command)


def show_list(results, page, query):
    clear_screen()
    total = len(results)
    pages = max(1, (total + PAGE - 1) // PAGE)
    page = max(0, min(page, pages - 1))
    chunk = results[page * PAGE: page * PAGE + PAGE]
    top = results[0][0] if results else 1.0

    print(dim(f'"{query}"   {total} results   page {page + 1}/{pages}'))
    print()

    width = shutil.get_terminal_size().columns
    for n, (score, case) in enumerate(chunk, page * PAGE + 1):
        # pct = round(score / top * 100) if top else 0
        prefix = f'  {n:>3})  '
        wrapped = textwrap.fill(
            first_line(case),
            width=width,
            initial_indent=prefix,
            subsequent_indent=' ' * len(prefix),
        )
        print(highlight(wrapped, query))
        print()

    nav = '  [number] open   '
    nav += '[n] next   ' if page + 1 < pages else ''
    nav += '[p] prev   ' if page > 0 else ''
    nav += '[b] back'
    print(dim(nav))
    print()
    return page


def show_case(case, query=""):
    clear_screen()
    lines = case["text"].strip().splitlines()
    title = next((ln.strip() for ln in lines if ln.strip()), "(untitled)")
    body = "\n".join(lines[1:]).strip() if len(lines) > 1 else ""
    print(dim(f'── {case.get("source", "")} ' + '─' * 20))
    print(highlight(highlight_links(title), query))
    if body:
        print()
        print(highlight(highlight_links(body), query))
    print()
    print(dim('  [e] edit case   [↵] reload   [b] back   [number] open case   [h] help   [q] quit'))
    print()


def first_line(case):
    for ln in case["text"].splitlines():
        if ln.strip():
            return ln.strip()
    return "(empty)"
