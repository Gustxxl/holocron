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

_SWITCH_NOTES = {
    'local': 'The server is off, answering from this computer.',
    'server': 'Back on the server.',
    None: "I can't reach a model right now, searching by words.",
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
        sys.stdout.write('\r\033[2K\033[?25h')
        sys.stdout.flush()

    def _run(self):
        i = 0
        while not self._stop.is_set():
            line = f'  {self.label}{"." * (i % 3 + 1)}'
            sys.stdout.write('\r\033[2K' + dim(line[:_width()]))
            sys.stdout.flush()
            i += 1
            self._stop.wait(0.4)


def _ask(question, thinking):
    thinking.label = 'Looking through the archive'
    archives.load()
    r = keeper.ask(archives.cases(), question)
    state = {
        'question': question, 'kind': 'empty', 'summary': '', 'lines': [],
        'sources': [], 'terms': ' '.join(r['terms']), 'online': r['online'],
        'via': r['via'], 'start': 0,
    }
    if r['picked']:
        thinking.label = 'Reading the record'
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
    elif r['similar']:
        state.update(kind='similar', sources=r['similar'][:MAX_SOURCES])
    return state


def _print_answer(state):
    print()
    kind = state['kind']
    if kind == 'empty':
        _say("I couldn't find anything about this in the archive.")
    elif kind == 'answer':
        _say(state['summary'] or 'Here is what the archive says:')
        if state['lines']:
            print()
            for ln in state['lines']:
                _quote(ln, state['terms'])
    elif state['online']:
        _say("I don't have an exact answer. These records look closest:")
    else:
        _say('Here is a plain search:')

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
        _say("I'm not connected yet, so I can only search by words. "
             'Set me up in settings > Archive > Keeper.')
    else:
        _say('Ask me anything about your archive.')
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

        with _Thinking() as thinking:
            state = _ask(command, thinking)
        if state['via'] != via:
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
        elif state['kind'] == 'empty':
            haptic('warning')
        else:
            haptic('tap')
