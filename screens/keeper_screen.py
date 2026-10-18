import contextlib
import io
import shutil
import sys
import textwrap
from core import archives, keeper
from core.commands import HELP_SECTIONS
from screens.help_screen import render_help
from screens.search_screen import open_case, first_line, highlight, highlight_links
from ui.interface import Spinner, clear_screen, dim, haptic, nav_line, num, pause, read_command, wait

MIN_QUESTION = 3
GREETING_ROW = 3
NAV_ROWS = 2

LINES = {
    'connecting': 'Waking Keeper',
    'ready': 'Awaiting your query...',
    'ready_case': 'Ask about this record.',
    'not_connected': 'No model connected. Search by words only. Settings > Archive > Keeper.',
    'unset': 'No model and no archive. Configure in settings > Archive.',
    'short': 'Type at least 3 characters.',
    'silent': 'Keeper has nothing to add.',
    'empty': 'Nothing in the archive on this.',
    'similar': 'Closest records:',
    'plain': 'Search by words:',
    'outside': 'Not from the archive.',
    'to_local': 'Server unavailable. Running on this computer.',
    'to_server': 'Server restored.',
    'to_none': 'No model reachable. Searching by words.',
    'thinking': 'Considering',
    'searching': 'Searching the archive',
    'reading': 'Reading the records',
    'searched': 'Searched:',
}

_SWITCH_NOTES = {
    'local': LINES['to_local'],
    'server': LINES['to_server'],
    None: LINES['to_none'],
}

_SESSION = {'turns': [], 'records': []}


def _width():
    return shutil.get_terminal_size().columns - 1


def _fill(text):
    return '\n'.join(
        textwrap.fill(ln, width=_width(), initial_indent='  ', subsequent_indent='  ',
                      break_long_words=False, break_on_hyphens=False) if ln.strip() else ''
        for ln in text.splitlines()
    )


def _say(text):
    print(highlight_links(_fill(text)))


def _aside(text):
    print(dim(_fill(text)))


def _quote(line, terms):
    wrapped = textwrap.fill(line, width=_width(), initial_indent='  │ ', subsequent_indent='  │ ',
                            break_long_words=False, break_on_hyphens=False)
    print(highlight_links(highlight(wrapped, terms)))


def _source(n, case, digits):
    archive = case.get('archive', '')
    title = first_line(case)
    room = _width() - digits - 7 - len(archive)
    if len(title) > room:
        title = title[:max(room, 10) - 1] + '…'
    print(f'{num(n, digits)}{title}  ' + dim(f'({archive})'))


def _switch_note(via):
    if via == 'local' and not keeper.has_server():
        return None
    return _SWITCH_NOTES[via]


def _drop_greeting(row, rows):
    sys.stdout.write(f'\0337\033[{row};1H\033[{rows}M\0338\033[{rows}A')
    sys.stdout.flush()


def _nav(turns, records):
    nav = [('number', 'open record', '#', 'open')] if records else []
    if turns:
        nav.append(('c', 'clear'))
    nav += [('b', 'back'), ('h', 'help')]
    print(dim(nav_line(nav, _width())))
    print()


def _drop_nav(command):
    cols = shutil.get_terminal_size().columns
    up = (len('Keeper> ' + command) - 1) // cols + 1 + NAV_ROWS
    sys.stdout.write(f'\033[{up}A\033[{NAV_ROWS}M\033[{up - NAV_ROWS}B')
    sys.stdout.flush()


def _ask(question, turns, records, focus, thinking):
    archives.load()
    cases = archives.cases()
    if not cases and keeper.active() is None:
        return {'question': question, 'kind': 'unset', 'reply': '', 'quotes': [], 'sources': [],
                'cited': 0, 'archive': False, 'lookup': False, 'terms': '', 'online': False, 'via': None, 'links': []}

    def step(key):
        thinking.label = LINES[key]

    state = keeper.reply(question, keeper.history(turns), cases, records, focus, step)
    state.update(question=question, kind='reply')
    state['via'] = keeper.current_slot() if state['online'] else None
    return state


def _short(question):
    return {'question': question, 'kind': 'short', 'reply': '', 'quotes': [], 'sources': [],
            'cited': 0, 'archive': False, 'lookup': False, 'terms': '', 'online': False, 'via': None, 'links': []}


def _print_answer(state):
    print()
    kind = state['kind']
    if kind == 'unset':
        _say(LINES['unset'])
        print()
        return
    if kind == 'short':
        _aside(LINES['short'])
        print()
        return

    if state['reply']:
        _say(state['reply'])
        if state['quotes']:
            print()
            for ln in state['quotes']:
                _quote(ln, state['terms'])
        if state.get('links'):
            print()
            print(dim('  Link' if len(state['links']) == 1 else '  Links'))
            for url, label in state['links']:
                print(f'    {label}  {highlight_links(url)}' if label else f'    {highlight_links(url)}')
        if state['lookup'] and not state['archive']:
            print()
            _aside(LINES['outside'])
    elif state['online']:
        _say(LINES['similar'] if state['sources'] else LINES['silent'])
    else:
        _say(LINES['plain'] if state['sources'] else LINES['empty'])
        if not state['sources'] and state['terms']:
            _aside(f"{LINES['searched']} {', '.join(state['terms'].split())}")

    sources = state['sources']
    if sources:
        print()
        start, cited = state['start'], state['cited']
        digits = len(str(start + len(sources) - 1))
        if cited:
            print(dim('  Source'))
            for n, c in enumerate(sources[:cited], start):
                _source(n, c, digits)
            if len(sources) > cited:
                print(dim('  Related'))
        for n, c in enumerate(sources[cited:], start + cited):
            _source(n, c, digits)
    print()


def _draw(turns, records, focus, pending, conn):
    print(dim('Keeper'))
    if focus:
        print(num(1) + dim(first_line(focus)[:_width() - 4]))
    print()
    rows = 0
    if conn is None:
        _say(LINES['not_connected'])
        print()
    elif not turns and pending is None:
        _say(LINES['ready_case' if focus else 'ready'])
        rows = 2
        note = _switch_note(conn['slot'])
        if conn['slot'] == 'local' and note:
            print(dim('  ' + note))
            rows += 1
        print()
    for turn in turns:
        print(f"Keeper> {turn['question']}")
        _print_answer(turn)
    if pending:
        print(f'Keeper> {pending}')
    else:
        _nav(turns, records)
    return rows


def _redraw(turns, records, focus, pending=None, refresh=False):
    if (refresh or not keeper.cached()) and keeper.configured():
        clear_screen()
        print(dim('Keeper'))
        print()
        wait(LINES['connecting'], keeper.active, True)
    conn = keeper.active()
    frame = io.StringIO()
    with contextlib.redirect_stdout(frame):
        rows = _draw(turns, records, focus, pending, conn)
    clear_screen()
    sys.stdout.write(frame.getvalue())
    sys.stdout.flush()
    return (conn['slot'] if conn else None), rows


def _terms_for(turns, number):
    for turn in turns:
        if turn.get('start', 0) <= number < turn.get('start', 0) + len(turn['sources']):
            return turn['terms']
    return ''


def keeper_screen(case=None):
    session = {'turns': [], 'records': [case]} if case else _SESSION
    turns, records = session['turns'], session['records']
    row = GREETING_ROW + (1 if case else 0)
    via, greeting = _redraw(turns, records, case)

    while True:
        command = read_command('Keeper> ')
        low = command.lower()
        if low in ('b', 'back'):
            return
        if low in ('h', 'help'):
            clear_screen()
            render_help(HELP_SECTIONS)
            pause()
            via, greeting = _redraw(turns, records, case)
            continue
        if low in ('s', 'settings'):
            from screens.settings_screen import settings_screen
            settings_screen()
            via, greeting = _redraw(turns, records, case)
            continue
        if low == 'c' and turns:
            turns.clear()
            del records[1 if case else 0:]
            via, greeting = _redraw(turns, records, case)
            continue
        if command == '':
            via, greeting = _redraw(turns, records, case, refresh=True)
            continue
        if command.isdigit():
            number = int(command)
            if not 1 <= number <= len(records):
                continue
            results = [(0, c) for c in records]
            new = open_case(results, number, _terms_for(turns, number), rerun=False)
            if not new or new == 'l' or len(new) < MIN_QUESTION:
                via, greeting = _redraw(turns, records, case)
                continue
            command = new
            _redraw(turns, records, case, command)
        else:
            _drop_nav(command)
            if greeting:
                _drop_greeting(row, greeting)
        greeting = 0

        if len(command.strip()) < MIN_QUESTION and keeper.active() is None:
            state = _short(command)
        else:
            with Spinner(LINES['thinking']) as thinking:
                state = _ask(command, turns, records, case, thinking)
        if state['kind'] == 'reply' and state['via'] != via:
            note = _switch_note(state['via'])
            if note:
                print()
                print(dim('  ' + note))
            via = state['via']
        state['start'] = len(records) + 1
        records.extend(state['sources'])
        turns.append(state)
        _print_answer(state)
        _nav(turns, records)

        if state['archive']:
            haptic('confirm')
        elif state['kind'] in ('unset', 'short') or not (state['reply'] or state['sources']):
            haptic('warning')
        else:
            haptic('tap')
