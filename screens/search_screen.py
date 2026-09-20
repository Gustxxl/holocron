import re
import difflib
from core import archive, search
from ui.interface import clear_screen, dim, pause, read_command, error_haptic
from core import archive


_HL = "\033[1;38;2;116;167;254m"
_RESET = "\033[0m"


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


def search_screen(initial_query=None):
    cases = archive.cases()
    if not cases:
        clear_screen()
        print("No excalidraw scenes found.")
        pause()
        return

    query = (initial_query or "").strip()
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
            print(dim('  [type] search   [b] back'))
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

        if low in ('b', 'back'):
            return
        if command == '':
            archive.load()
            cases = archive.cases()
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

        query = command
        results = search.search(cases, query)
        page = 0


def open_case(results, number, query):
    while 1 <= number <= len(results):
        show_case(results[number - 1][1], query)
        command = read_command('case> ')
        low = command.lower()
        if low in ('b', 'back'):
            return
        if command == '':
            archive.load()
            if query:
                results = search.search(archive.cases(), query)
            continue
        if command.isdigit():
            number = int(command)



def show_list(results, page, query):
    clear_screen()
    total = len(results)
    pages = max(1, (total + PAGE - 1) // PAGE)
    page = max(0, min(page, pages - 1))
    chunk = results[page * PAGE: page * PAGE + PAGE]
    print(dim(f'Search: "{query}"   ·   {total} found   ·   page {page + 1}/{pages}'))
    print()
    for n, (score, case) in enumerate(chunk, page * PAGE + 1):
        print(f'  {n:>3}) {highlight(first_line(case), query)}')
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
    print(highlight(title, query))
    if body:
        print()
        print(highlight(body, query))
    print()
    print(dim('  [↵] reload   [b] back   [number] open   [q] quit'))
    print()


def first_line(case):
    for ln in case["text"].splitlines():
        if ln.strip():
            return ln.strip()
    return "(empty)"
