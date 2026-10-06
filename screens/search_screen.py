import re
import difflib
import shutil
import textwrap
from core import archives, search, excalidraw
from core.commands import HELP_SECTIONS
from core.editor import edit_text
from screens.help_screen import render_help
from ui.interface import clear_screen, dim, pause, read_command, error_haptic
from ui.markdown import render_tables, table_cells


_HL = '\033[1;38;2;116;167;254m'
_RESET = '\033[0m'

PAGE = 8
LIST_PAGE = 15
MIN_QUERY = 3

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
            return f'{_HL}{word}{_RESET}'
        return word

    return re.sub(r'\w+', repl, text, flags=re.UNICODE)


def _all(cases):
    return [(0, c) for c in sorted(cases, key=lambda c: first_line(c).lower())]


def _run(cases, text):
    if text.lower() in ('l', 'list'):
        return _all(cases), '', True
    return search.search(cases, text), text, False


def _too_short(text):
    return len(text) < MIN_QUERY and text.lower() not in ('l', 'list')


def search_screen(initial_query=None):
    cases = archives.cases()
    if not cases:
        clear_screen()
        print('No scenes found.')
        print(dim('Add an archive path in settings.'))
        pause()
        return

    query = (initial_query or '').strip()
    results, list_mode, page = [], False, 0

    if query and _too_short(query):
        clear_screen()
        print(f'Type at least {MIN_QUERY} characters.')
        pause()
        return
    if query:
        results, query, list_mode = _run(cases, query)

    while True:
        if query and not results:
            clear_screen()
            print(f"Nothing found for '{query}'.")
            tips = search.suggest(cases, query)
            if tips:
                print(dim('Maybe: ' + ', '.join(tips)))
            print()
            print(dim('  [b] back   [h] help'))
            print()
            error_haptic()
        elif results:
            ps = LIST_PAGE if list_mode else PAGE
            page = show_list(results, page, query, ps)
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
            new_query = open_case(results, int(command), query)
            if new_query:
                archives.load()
                cases = archives.cases()
                results, query, list_mode = _run(cases, new_query)
                page = 0
            continue

        if _too_short(command):
            clear_screen()
            print(f'Type at least {MIN_QUERY} characters.')
            pause()
            continue

        archives.load()
        cases = archives.cases()
        results, query, list_mode = _run(cases, command)
        page = 0


def _refresh(results, query, rerun):
    archives.load()
    if rerun and query:
        return search.search(archives.cases(), query)
    return results


def open_case(results, number, query, rerun=True):
    while 1 <= number <= len(results):
        show_case(results[number - 1][1], query, number, len(results))
        command = read_command('case> ')
        low = command.lower()

        if low in ('e', 'edit'):
            case = results[number - 1][1]
            fp = case.get('filepath')
            eid = case.get('element_id')

            if not fp or not eid:
                print(dim('  Editing not available for this case'))
                pause()
                continue

            original = case['text']
            edited = edit_text(original).strip()

            if not edited:
                print(dim('  Empty text — edit cancelled'))
                pause()
                continue

            if edited == original:
                print(dim('  No changes'))
                pause()
                continue

            clear_screen()
            print(dim('  Old:'))
            print(f'  {original[:200]}')
            print()
            print(dim('  New:'))
            print(f'  {edited[:200]}')
            print()
            confirm = read_command('  Save changes? [y/n]> ')
            if confirm.lower() != 'y':
                print(dim('  Cancelled'))
                pause()
                continue

            try:
                if fp.endswith('.md'):
                    excalidraw.update_text_obsidian(fp, eid, edited)
                else:
                    excalidraw.update_text(fp, eid, edited)
                case['text'] = edited
                print(dim('  Saved'))
                results = _refresh(results, query, rerun)
            except Exception as e:
                print(f'  Error: {e}')
            pause()
            continue

        if low in ('l', 'list'):
            return 'l'
        if low in ('s', 'settings'):
            from screens.settings_screen import settings_screen
            settings_screen()
            results = _refresh(results, query, rerun)
            continue
        if low in ('h', 'help'):
            clear_screen()
            render_help(HELP_SECTIONS)
            pause()
            continue
        if low in ('b', 'back'):
            return None
        if command == '':
            results = _refresh(results, query, rerun)
            continue
        if low == 'n':
            if number < len(results):
                number += 1
            continue
        if low == 'p':
            if number > 1:
                number -= 1
            continue
        if command.isdigit():
            number = int(command)
            continue

        q = command.strip()
        if len(q) >= MIN_QUERY:
            return q

    return None


def show_list(results, page, query, page_size=PAGE, note=None):
    clear_screen()
    total = len(results)
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    chunk = results[page * page_size: page * page_size + page_size]

    if note:
        header = note
    elif query:
        header = f'Search: "{query}"   {total} results'
    else:
        header = f'{total} cases'
    if pages > 1:
        header += f'   {page + 1}/{pages}'
    print(dim(header))
    print()

    width = shutil.get_terminal_size().columns - 1
    for n, (score, case) in enumerate(chunk, page * page_size + 1):
        prefix = f'  {n:>3})  '
        wrapped = textwrap.fill(
            first_line(case),
            width=width,
            initial_indent=prefix,
            subsequent_indent=' ' * len(prefix),
            break_long_words=False,
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


def show_case(case, query='', number=None, total=None):
    clear_screen()
    name = case.get('source', '')
    for suffix in ('.excalidraw.md', '.excalidraw', '.md'):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    archive = case.get('archive', '')

    text = case['text'].strip()
    lines = text.splitlines()
    first = next((ln.strip() for ln in lines if ln.strip()), '')
    if first.startswith('|'):
        title, body = name, text
    else:
        title = first or '(untitled)'
        body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ''

    width = shutil.get_terminal_size().columns - 1
    pos = f'{number}/{total}  ' if number else ''
    print(dim(f'── {pos}{name} ({archive}) ' + '─' * 20))
    print()
    print(highlight(highlight_links(_wrap(title, width)), query))
    if body:
        print()
        print(highlight(highlight_links(_wrap(render_tables(body), width)), query))
    print()
    nav = '  [e] edit   '
    nav += '[n] next   ' if number and number < total else ''
    nav += '[p] prev   ' if number and number > 1 else ''
    nav += '[b] back   [h] help'
    print(dim(nav))
    print()


def first_line(case):
    for ln in case['text'].splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith('|'):
            return '  '.join(c for c in table_cells(ln) if c)
        return ln
    return '(empty)'


def _wrap(text, width):
    out = []
    for ln in text.splitlines():
        if not ln.strip() or ln[0] in '┌│├└':
            out.append(ln)
            continue
        indent = ln[:len(ln) - len(ln.lstrip())]
        if ln.lstrip().startswith(('- ', '* ', '+ ')):
            indent += '  '
        out.append(textwrap.fill(
            ln,
            width=width,
            subsequent_indent=indent,
            break_long_words=False,
        ))
    return '\n'.join(out)
