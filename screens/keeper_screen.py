import json
import shutil
import sys
import textwrap
import threading
from core import archives, keeper
from core.commands import HELP_SECTIONS
from screens.help_screen import render_help
from screens.search_screen import open_case, first_line, highlight
from ui.interface import clear_screen, dim, pause, read_command, haptic

MIN_QUESTION = 3
MAX_SOURCES = 5
HISTORY_TURNS = 4

LINES = {
    'ready': 'Awaiting your query...',
    'not_connected': 'No model connected. Search by words only. Settings > Archive > Keeper.',
    'unset': 'No model and no archive. Configure in settings > Archive.',
    'silent': 'No response.',
    'empty': 'Nothing in the archive on this.',
    'answer': 'From the archive:',
    'similar': 'No exact match. Closest records:',
    'plain': 'Search by words:',
    'to_local': 'Server unavailable. Running on this computer.',
    'to_server': 'Server restored.',
    'to_none': 'No model reachable. Searching by words.',
    'thinking': 'Considering',
    'searching': 'Searching the archive',
    'reading': 'Reading the record',
}

_SWITCH_NOTES = {
    'local': LINES['to_local'],
    'server': LINES['to_server'],
    None: LINES['to_none'],
}


def _width():
    return shutil.get_terminal_size().columns - 1


def _say(text):
    print(textwrap.fill(text, width=_width(), initial_indent='  ',
                        subsequent_indent='  ', break_long_words=False))


def _quote(line, terms):
    wrapped = textwrap.fill(line, width=_width(), initial_indent='  │ ',
                            subsequent_indent='  │ ', break_long_words=False)
    print(highlight(wrapped, terms))


def _source(n, case):
    archive = case.get('archive', '')
    title = first_line(case)
    room = _width() - 12 - len(archive)
    if len(title) > room:
        title = title[:max(room, 10) - 1] + '…'
    print(f'    {n}) {title}  ' + dim(f'({archive})'))


def _switch_note(via):
    if via == 'local' and not keeper.has_server():
        return None
    return _SWITCH_NOTES[via]


class _Thinking:
    def __init__(self):
        self.label = ''
        self._stop = threading.Event()
        self._thread = threading.Thread(target=self._run, daemon=True)

    def __enter__(self):
        sys.stdout.write('\033[?25l')
        sys.stdout.flush()
        self._thread.start()
        return self

    def __exit__(self, *exc):
        self._stop.set()
        self._thread.join()
        sys.stdout.write('\r\033[2K\033[1A\033[?25h')
        sys.stdout.flush()

    def _run(self):
        i = 0
        while not self._stop.is_set():
            line = f'  {self.label}{"." * (i % 3 + 1)}'
            sys.stdout.write('\r\033[2K' + dim(line[:_width()]))
            sys.stdout.flush()
            i += 1
            self._stop.wait(0.4)


def _history(turns):
    out = []
    for t in [t for t in turns if t['kind'] == 'chat' and t['reply']][-HISTORY_TURNS:]:
        out.append({'role': 'user', 'content': t['question']})
        out.append({'role': 'assistant', 'content': json.dumps({'reply': t['reply']}, ensure_ascii=False)})
    return out


def _ask(question, history, thinking):
    thinking.label = LINES['thinking']
    archives.load()
    cases = archives.cases()
    route = keeper.route(question)
    state = {
        'question': question, 'kind': 'empty', 'summary': '', 'lines': [], 'reply': '',
        'sources': [], 'terms': ' '.join(route['terms']), 'online': route['online'],
        'via': None, 'start': 0,
    }

    if not cases and not route['online']:
        state['kind'] = 'unset'
        return state

    talk = not cases or (route['intent'] == 'chat' and not route['terms'])
    if not talk:
        thinking.label = LINES['searching']
        r = keeper.find(cases, question, route['terms'], route['online'])
        state.update(terms=' '.join(r['terms']), online=r['online'])
        if r['picked']:
            thinking.label = LINES['reading']
            try:
                ans = keeper.answer(question, r['picked'][0])
            except keeper.KeeperOffline:
                ans = {'summary': '', 'lines': []}
            rest = [c for c in r['similar'] if all(c is not p for p in r['picked'])]
            state['sources'] = (r['picked'] + rest)[:MAX_SOURCES]
            if ans['summary'] or ans['lines']:
                state.update(kind='answer', summary=ans['summary'], lines=ans['lines'])
            else:
                state['kind'] = 'similar'
        elif route['intent'] == 'chat' and r['online']:
            talk = True
        elif r['similar']:
            state.update(kind='similar', sources=r['similar'][:MAX_SOURCES])

    if talk and state['online']:
        thinking.label = LINES['thinking']
        try:
            reply = keeper.chat(question, history)
        except keeper.KeeperOffline:
            reply = ''
            state['online'] = False
        state.update(kind='chat', reply=reply, sources=[], terms='')

    state['via'] = keeper.current_slot() if state['online'] else None
    return state


def _print_answer(state):
    print()
    kind = state['kind']
    if kind == 'unset':
        _say(LINES['unset'])
    elif kind == 'chat':
        _say(state['reply'] or LINES['silent'])
    elif kind == 'empty':
        _say(LINES['empty'])
    elif kind == 'answer':
        _say(state['summary'] or LINES['answer'])
        if state['lines']:
            print()
            for ln in state['lines']:
                _quote(ln, state['terms'])
    elif state['online']:
        _say(LINES['similar'])
    else:
        _say(LINES['plain'])

    sources = state['sources']
    if sources:
        print()
        start = state['start']
        if kind == 'answer':
            print(dim('  Source'))
            _source(start, sources[0])
            if len(sources) > 1:
                print(dim('  Related'))
                for n, c in enumerate(sources[1:], start + 1):
                    _source(n, c)
        else:
            for n, c in enumerate(sources, start):
                _source(n, c)
    print()


def _redraw(turns):
    clear_screen()
    print(dim('Keeper'))
    print()
    conn = keeper.active(refresh=True)
    if conn is None:
        _say(LINES['not_connected'])
    elif not turns:
        _say(LINES['ready'])
        note = _switch_note(conn['slot'])
        if conn['slot'] == 'local' and note:
            print(dim('  ' + note))
    print()
    print(dim('  [number] open record   [b] back   [h] help'))
    print()
    for turn in turns:
        print(dim(f"Keeper> {turn['question']}"))
        _print_answer(turn)
    return conn['slot'] if conn else None


def _owner(turns, number):
    for turn in turns:
        if turn['start'] <= number < turn['start'] + len(turn['sources']):
            return turn
    return None


def keeper_screen():
    turns = []
    records = []
    via = _redraw(turns)

    while True:
        command = read_command('Keeper> ')
        low = command.lower()
        if low in ('b', 'back'):
            return
        if low in ('h', 'help'):
            clear_screen()
            render_help(HELP_SECTIONS)
            pause()
            via = _redraw(turns)
            continue
        if low in ('s', 'settings'):
            from screens.settings_screen import settings_screen
            settings_screen()
            via = _redraw(turns)
            continue
        if command == '':
            via = _redraw(turns)
            continue
        if command.isdigit():
            number = int(command)
            turn = _owner(turns, number)
            if not turn:
                continue
            results = [(0, c) for c in records]
            new = open_case(results, number, turn['terms'], rerun=False)
            via = _redraw(turns)
            if not new or new == 'l':
                continue
            command = new
            print(f'Keeper> {command}')
        if len(command) < MIN_QUESTION:
            continue

        print()
        with _Thinking() as thinking:
            state = _ask(command, _history(turns), thinking)
        if state['kind'] != 'unset' and state['via'] != via:
            note = _switch_note(state['via'])
            if note:
                print()
                print(dim('  ' + note))
            via = state['via']
        state['start'] = len(records) + 1
        records.extend(state['sources'])
        turns.append(state)
        _print_answer(state)

        if state['kind'] == 'answer':
            haptic('confirm')
        elif state['kind'] in ('empty', 'unset'):
            haptic('warning')
        else:
            haptic('tap')
