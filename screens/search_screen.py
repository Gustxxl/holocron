import re
import shutil
import textwrap
from pathlib import Path
from core import archives, search, excalidraw, favorites, checklist, editor, wikilinks, keeper
from core.archives.vault import Vault, save_note, create_note, read_note
from core.commands import HELP_SECTIONS
from core.settings import new_cases_path, search_separator
from core.system import copy_text
from screens.help_screen import render_help
from ui.interface import clear_screen, dim, error, pause, read_command, error_haptic, haptic, underline, nav_line
from ui.markdown import code_blocks, is_code, links, paint_code, render_tables, table_cells
from ui.note import render_note
from ui.format import plural


_HL = '\033[38;2;116;167;254m'
_MARK = '\033[38;2;20;20;20;48;2;116;167;254m'
_RESET = '\033[0m'

PAGE = 10
LIST_PAGE = 15
MIN_QUERY = 3

_URL_RE = re.compile(r'https?://\S+')
_CHECK_RE = re.compile(r'x\s*(\d+)')
_JUMP_RE = re.compile(r'j\s*(\d*)')
_LINK_RE = re.compile('\xa0\x03(\\d+)\x04')


def _link_mark(shown, n):
    return f'{shown}\xa0\x03{n}\x04'


def _marks(text):
    return _LINK_RE.sub(lambda m: ' ' + dim(f'[{m.group(1)}]'), text)


def highlight_links(text):
    return _URL_RE.sub(lambda m: dim(underline(m.group())), text)


def _hl_match(qw, tw):
    tw = tw.replace('ё', 'е')
    if not search._WORD_RE.fullmatch(qw):
        return qw in tw
    return search.word_match(qw, tw) > 0


def _phrase_re(queries):
    patterns = []
    for query in queries:
        parts = [re.escape(p) for p in re.split(r'[\s_]+', query.lower().replace('ё', 'е')) if p]
        if parts:
            patterns.append(r'[ \t_]+'.join(parts).replace('е', '[её]'))
    if not patterns:
        return None
    patterns.sort(key=len, reverse=True)
    return re.compile(rf'(?<!\w)(?:{"|".join(patterns)})(?!\w)', re.IGNORECASE)


def highlight(text, *queries):
    terms = [t for q in queries for t in search._norm_words(q)]
    if not terms:
        return text

    def repl(m):
        word = m.group(0)
        if any(_hl_match(t, word.lower()) for t in terms):
            return f'{_HL}{word}{_RESET}'
        return word

    def soft(part):
        return re.sub(r'[^\W_]+', repl, part)

    def soft_no_urls(text):
        out, pos = [], 0
        for m in _URL_RE.finditer(text):
            out.append(soft(text[pos:m.start()]))
            out.append(m.group())
            pos = m.end()
        out.append(soft(text[pos:]))
        return ''.join(out)

    phrase = _phrase_re(queries)
    if not phrase:
        return soft_no_urls(text)
    out, pos = [], 0
    for m in phrase.finditer(text):
        out.append(soft_no_urls(text[pos:m.start()]))
        out.append(f'{_MARK}{m.group(0)}{_RESET}')
        pos = m.end()
    out.append(soft_no_urls(text[pos:]))
    return ''.join(out)


def _all(cases):
    pinned = favorites.resolve(cases)
    ids = {id(c) for c in pinned}
    return [(0, c) for c in [*pinned, *by_name(c for c in cases if id(c) not in ids)]]


def _parts(query):
    return [p for p in search.split(query, search_separator()) if len(p) >= MIN_QUERY]


def _find(cases, query):
    parts = _parts(query)
    if len(parts) < 2:
        return search.search(cases, parts[0] if parts else query), None
    groups, missing = search.search_many(cases, parts)
    named = [(p, g, sum(1 for s, _ in g if search.is_exact(s))) for p, g in zip(parts, groups) if g]
    share = max(PAGE // len(named), 1) if named else 0
    results, layout, taken = [], [], [0] * len(named)
    while any(taken[i] < len(g) for i, (_, g, _) in enumerate(named)):
        for i, (part, group, top) in enumerate(named):
            chunk = group[taken[i]:taken[i] + share]
            if not chunk:
                continue
            if layout and layout[-1][0] == part:
                last = layout[-1]
                layout[-1] = (part, last[1], last[2] + len(chunk), *last[3:])
            else:
                layout.append((part, len(results), len(chunk), taken[i], len(group), top))
            results += chunk
            taken[i] += len(chunk)
    return results, (layout, missing)


def _group_at(layout, i):
    return next((g for g in layout if g[1] <= i < g[1] + g[2]), None)


def _suggest(cases, query):
    parts = _parts(query)
    fixed = [(search.suggest(cases, p) or [p])[0] for p in parts]
    return [f'{search_separator()} '.join(fixed)] if fixed != parts else []


def _run(cases, text):
    if text.lower() in ('l', 'list'):
        return _all(cases), None, '', True
    results, groups = _find(cases, text)
    return results, groups, text, False


def _too_short(text):
    return not _parts(text) and text.lower() not in ('l', 'list')


def _as_query(text):
    sep = search_separator()
    return text.replace(sep, ' ') if sep else text


def _exact(results, query, list_mode):
    if list_mode or not query:
        return None
    return sum(1 for score, _ in results if search.is_exact(score))


def search_screen(initial_query=None):
    cases = archives.cases()
    if not cases:
        clear_screen()
        if archives.missing():
            print('Archive not found — check settings.')
        else:
            print('No archive set — add a path in settings.')
        pause()
        return
    query = (initial_query or '').strip()
    results, groups, list_mode, page = [], None, False, 0
    exact, exact_for = None, None
    if query and _too_short(query):
        clear_screen()
        print(f'Type at least {MIN_QUERY} characters.')
        pause()
        return
    if query:
        results, groups, query, list_mode = _run(cases, query)
    while True:
        if query and not results:
            clear_screen()
            print(f"Nothing found for '{query}'.")
            tips = _suggest(cases, query)
            if tips:
                print(dim('Maybe: ' + ', '.join(tips)))
            print()
            print(dim('  [b] back   [h] help'))
            print()
            error_haptic()
        elif results:
            if exact_for is not results:
                exact, exact_for = _exact(results, query, list_mode), results
            ps = LIST_PAGE if list_mode else PAGE
            page = show_list(results, page, query, ps, exact=exact, groups=groups)
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
                results, groups = _find(cases, query)
            continue
        if low in ('b', 'back'):
            return
        if command == '':
            if not results:
                return
            archives.load(force=True)
            cases = archives.cases()
            if query:
                results, groups = _find(cases, query)
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
                results, groups, query, list_mode = _run(cases, new_query)
                page = 0
            continue
        if _too_short(command):
            clear_screen()
            print(f'Type at least {MIN_QUERY} characters.')
            pause()
            continue
        archives.load()
        cases = archives.cases()
        results, groups, query, list_mode = _run(cases, command)
        page = 0


def create_case():
    text = editor.edit_text('')
    if text is None:
        error('Could not open the editor')
        return
    if not text.strip():
        return
    path = create_note(new_cases_path(), text)
    if path is None:
        error('Could not create the note')
        return
    haptic('success')
    archives.load()
    target = Path(path).resolve()
    found = [(0, c) for c in archives.cases()
             if c.get('archive') == Vault.name and Path(c['filepath']).resolve() == target]
    if not found:
        return
    new_query = open_case(found, 1, '', rerun=False)
    if new_query:
        search_screen(new_query)


def _refresh(results, query, rerun, force=False):
    archives.load(force)
    cases = archives.cases()
    if rerun and query:
        return _find(cases, query)[0]
    fresh = {(c.get('filepath'), c.get('element_id')): c for c in cases}
    return [(s, fresh.get((c.get('filepath'), c.get('element_id')), c)) for s, c in results]


def _confirm(prompt):
    return input(f'  {prompt} [y/N] ').strip().lower() in ('y', 'yes')


def _save(case, text):
    fp, eid = case.get('filepath'), case.get('element_id')
    if case.get('archive') == Vault.name:
        if read_note(fp) != case['text']:
            raise ValueError('the note changed on disk, open it again')
        save_note(fp, text)
    elif fp.endswith('.md'):
        excalidraw.update_text_obsidian(fp, eid, text, case.get('raw'))
    else:
        excalidraw.update_text(fp, eid, text, case.get('raw'))
    case['text'] = text
    if 'raw' in case:
        case['raw'], case['text'] = text, excalidraw.strip_emoji(text).strip()


def open_case(results, number, query, rerun=True, trail=()):
    while 1 <= number <= len(results):
        case = results[number - 1][1]
        jumps = show_case(case, query, number, len(results), trail)
        command = read_command('case> ')
        low = command.lower()

        if low in ('e', 'edit') and editor.available():
            if not case.get('filepath') or not case.get('element_id'):
                print(dim('  Editing not available for this case'))
                pause()
                continue
            results = _refresh(results, query, False)
            case = results[number - 1][1]
            source = case.get('raw', case['text'])
            edited = editor.edit_text(source)
            if edited is None:
                error('Could not open the editor')
                continue
            edited = edited.strip()
            if edited == source.strip():
                continue
            if not edited and case.get('archive') != Vault.name:
                error('Empty text — edit cancelled')
                continue
            if not edited and not _confirm('Clear the note?'):
                continue
            try:
                _save(case, edited)
                haptic('success')
            except Exception as e:
                kept = ' — your text is copied' if copy_text(edited) else ''
                error(f'Could not save: {e}{kept}')
            results = _refresh(results, query, False)
            continue

        if low in ('f', 'fav'):
            if case.get('filepath'):
                favorites.toggle(case)
                haptic('toggle')
            continue
        m = _CHECK_RE.fullmatch(low)
        if m and case.get('filename'):
            results = _refresh(results, query, False)
            case = results[number - 1][1]
            text = checklist.toggle(case['text'], int(m.group(1)))
            if text is None:
                continue
            try:
                _save(case, text)
                haptic('toggle')
            except Exception as e:
                print(f'  Error: {e}')
                pause(feedback='error')
            results = _refresh(results, query, False)
            continue
        m = _JUMP_RE.fullmatch(low)
        if m:
            n = int(m.group(1)) if m.group(1) else (1 if len(jumps) == 1 else 0)
            if 1 <= n <= len(jumps) and isinstance(jumps[n - 1], str):
                search_screen(_as_query(jumps[n - 1]))
                results = _refresh(results, query, False)
            elif 1 <= n <= len(jumps):
                target = [(0, c) for c in jumps[n - 1]]
                new_query = open_case(target, 1, '', rerun=False, trail=(*trail, first_line(case)))
                if new_query:
                    return new_query
                results = _refresh(results, query, False)
            continue

        if low in ('k', 'keeper') and keeper.configured():
            from screens.keeper_screen import keeper_screen
            keeper_screen(case)
            results = _refresh(results, query, False)
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
            results = _refresh(results, query, rerun, force=True)
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
        if _parts(q):
            return q
    return None


def list_rows(cases, start, total, width, query=''):
    digits = len(str(total))
    pad = ' ' * (digits + 3)
    terms = _parts(query)
    rows = []
    for i, case in enumerate(cases, start + 1):
        wrapped = textwrap.fill(first_line(case), width=width, initial_indent=pad, subsequent_indent=pad,
                                break_long_words=False, break_on_hyphens=False)
        rows.append(f'  {dim(str(i).rjust(digits))} {highlight(wrapped[len(pad):], *terms)}')
    return rows


def show_list(results, page, query, page_size=PAGE, note=None, exact=None, groups=None):
    clear_screen()
    total = len(results)
    pages = max(1, (total + page_size - 1) // page_size)
    page = max(0, min(page, pages - 1))
    start = page * page_size
    chunk = results[start: start + page_size]
    width = shutil.get_terminal_size().columns - 1
    layout, missing = groups or ((), ())
    count = plural(total, 'result') if query else plural(total, 'case')
    count += f'   {page + 1}/{pages}' if pages > 1 else ''
    if note:
        print(dim(_fit(note, width)))
    elif query and len(query) + len(count) + 13 <= width:
        print(dim(f'Search: "{query}"   {count}'))
    elif query:
        print(dim(count))
        print(dim(_asked(query, width, indent='')))
    else:
        print(dim(count))
    print()
    for part in missing:
        print(f"Nothing found for '{part}'.")
    if missing:
        print()
    if exact == 0 and not layout:
        print('No exact matches — showing similar cases.')
        print()
    for n, row in enumerate(list_rows([c for _, c in chunk], start, total, width, query), start + 1):
        if n > start + 1:
            print()
        group = _group_at(layout, n - 1)
        head = group and n - 1 in (group[1], start)
        if head:
            print(dim(f'  {group[0]} · {plural(group[4], "result")}'))
        if group:
            at, top = group[3] + n - 1 - group[1], group[5]
            similar = head and at >= top or bool(top) and at == top
        else:
            similar = exact and n == exact + 1
        if similar:
            print(dim('  Similar'))
        print(row)
    print()
    nav = [('number', 'open', '#', 'open')]
    if page + 1 < pages:
        nav.append(('n', 'next'))
    if page > 0:
        nav.append(('p', 'prev'))
    nav.append(('b', 'back'))
    nav.append(('h', 'help'))
    print(dim(nav_line(nav, width)))
    print()
    return page


def show_case(case, query='', number=None, total=None, trail=()):
    clear_screen()
    name = case.get('source', '')
    for suffix in ('.excalidraw.md', '.excalidraw', '.md'):
        if name.endswith(suffix):
            name = name[:-len(suffix)]
            break
    if case.get('filepath'):
        name = ''
    archive = case.get('archive', '')
    pinned = favorites.is_pinned(case)

    text, jumps = wikilinks.numbered(case.get('raw', case['text']).strip(), archives.cases(), _link_mark,
                                     here=case.get('filepath'))
    lines = text.splitlines()
    first = next((ln.strip() for ln in lines if ln.strip()), '')
    if case.get('filename'):
        title, body, name = case['filename'], text, ''
    elif first.startswith('|'):
        title, body = name, text
    else:
        title = first or '(untitled)'
        body = '\n'.join(lines[1:]).strip() if len(lines) > 1 else ''

    width = shutil.get_terminal_size().columns - 1
    pos = f'{number}/{total}  ' if number else ''
    mark = ' · pinned' if pinned else ''
    if trail:
        print(dim(_trail(trail, width)))
    for line in _case_head(pos, name, archive, mark, query, width):
        print(dim(line))
    fp = case.get('filepath')
    if fp:
        parts = Path(fp).parts
        short = str(Path(*parts[-3:])) if len(parts) > 3 else fp
        print(dim(f'   {short}'))
    print()
    terms = _parts(query)
    print(_marks(highlight_links(highlight(_wrap(links(title), width), *terms))))
    if body:
        if case.get('filename'):
            rendered = render_note(body, width)
        else:
            rendered = render_tables(_wrap(code_blocks(links(body)), width), width)
        print()
        print(_marks(highlight_links(paint_code(highlight(rendered, *terms)))))
    print()
    nav = []
    if editor.available():
        nav.append(('e', 'edit', 'e', 'edit'))
    if case.get('filename') and checklist.count(case['text']):
        nav.append(('x number', 'check', 'x#', 'check'))
    if jumps:
        if len(jumps) > 1:
            nav.append(('j number', 'jump', 'j#', 'jump'))
        else:
            nav.append(('j', 'jump', 'j', 'jump'))
    if keeper.configured():
        nav.append(('k', 'ask Keeper', 'k', 'ask'))
    if case.get('filepath'):
        nav.append(('f', 'unpin' if pinned else 'pin', 'f', 'unpin' if pinned else 'pin'))
    if number and number < total:
        nav.append(('n', 'next', 'n', 'next'))
    if number and number > 1:
        nav.append(('p', 'prev', 'p', 'prev'))
    nav.append(('b', 'back', 'b', 'back'))
    nav.append(('h', 'help', 'h', 'help'))
    print(dim(nav_line(nav, width)))
    print()
    return jumps


def first_line(case):
    if case.get('filename'):
        return case['filename']
    for ln in case['text'].splitlines():
        ln = ln.strip()
        if not ln:
            continue
        if ln.startswith('|'):
            return '  '.join(c for c in table_cells(links(ln)) if c)
        return links(ln)
    return '(empty)'


def by_name(cases):
    return sorted(cases, key=lambda c: first_line(c).casefold())


def _wrap(text, width):
    out = []
    for ln in text.splitlines():
        if not ln.strip() or is_code(ln) or ln.lstrip().startswith('|'):
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
            break_on_hyphens=False,
        ))
    return '\n'.join(out)


def _fit(text, width):
    return text if len(text) <= width else text[:max(width - 1, 0)].rstrip() + '…'


def _rule(text, width):
    return text + ' ' + '─' * max(width - len(text) - 1, 0)


def _asked(query, width, indent='   '):
    return textwrap.fill(f'"{query}"', width=width, initial_indent=indent, subsequent_indent=indent + ' ',
                         break_long_words=False, break_on_hyphens=False)


def _case_head(pos, name, archive, mark, query, width):
    labels = [f'{name} ({archive})', name] if name else [f'({archive})']
    line = f'── {pos}{labels[0]}{mark}'
    if query and len(line) + len(query) + 6 <= width:
        return [_rule(f'{line}  "{query}"', width)]
    if not query and len(line) + 2 <= width:
        return [_rule(line, width)]
    for label in labels:
        line = f'── {pos}{label}{mark}'
        if len(line) + 2 <= width:
            break
    lines = [_rule(_fit(line, width - 2), width)]
    if query:
        lines.append(_asked(query, width))
    return lines


def _trail(trail, width):
    items = list(trail)
    while len(items) > 1 and len(' › '.join(items)) > width:
        items = items[1:]
        if not items[0].startswith('… › '):
            items[0] = '… › ' + items[0]
    return _fit(' › '.join(items), width)
