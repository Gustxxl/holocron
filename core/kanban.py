import re

_FRONT_RE = re.compile(r'\A---\n(.*?)\n---[ \t]*(?:\n|\Z)', re.S)
_PLUGIN_RE = re.compile(r'^kanban-plugin:[ \t]*\S', re.M)
_LANE_RE = re.compile(r'^#{1,6}[ \t]+(.*?)[ \t]*$')
_CARD_RE = re.compile(r'^([-*+][ \t]+(?:\[(.)\][ \t]?)?)(.*)$')
_DONE_RE = re.compile(r'^\*\*[^*]+\*\*$')
_LIMIT_RE = re.compile(r'^(.+?)\s*\(\d+\)$')
_BLOCK_RE = re.compile(r'\s+\^([a-zA-Z0-9-]+)$')
_DEDENT_RE = re.compile(r'\n(?: {4}|\t)')
_SETTINGS = '%% kanban:settings'


def is_board(text):
    m = _FRONT_RE.match(text)
    return bool(m and _PLUGIN_RE.search(m.group(1)))


def _title(heading):
    heading = heading.replace('<br>', ' ').strip()
    m = _LIMIT_RE.match(heading)
    return m.group(1) if m else heading


def _card(lines, start, end):
    m = _CARD_RE.match(lines[start])
    body = '\n'.join([m.group(3), *lines[start + 1:end]]).replace('<br>', '\n').strip()
    first, sep, rest = _DEDENT_RE.sub('\n', body).strip().partition('\n')
    block = _BLOCK_RE.search(first)
    if block:
        first = first[:block.start()]
    return {'start': start, 'end': end, 'mark': m.group(1), 'check': m.group(2),
            'text': (first + sep + rest).strip(), 'block': block.group(1) if block else None}


def parse(text):
    lines = text.split('\n')
    front = _FRONT_RE.match(text)
    i = front.group(0).count('\n') if front else 0
    lanes = []
    while i < len(lines):
        ln = lines[i]
        if ln.startswith(_SETTINGS):
            break
        lane = lanes[-1] if lanes else None
        m = _LANE_RE.match(ln)
        if m:
            lanes.append({'title': _title(m.group(1)), 'head': i, 'complete': False, 'cards': []})
        elif lane and not lane['cards'] and _DONE_RE.match(ln.strip()):
            lane['complete'], lane['head'] = True, i
        elif lane and _CARD_RE.match(ln):
            end = i + 1
            while end < len(lines) and lines[end][:1] in (' ', '\t'):
                end += 1
            lane['cards'].append(_card(lines, i, end))
            i = end
            continue
        i += 1
    return lanes


def titles(text):
    return [lane['title'] for lane in parse(text)]


def _indent(lines, lanes):
    rest = (ln for lane in lanes for c in lane['cards'] for ln in lines[c['start'] + 1:c['end']])
    return '\t' if any(ln.startswith('\t') for ln in rest) else '    '


def _lines(mark, text, block, indent):
    first, *rest = text.strip().split('\n')
    if block:
        first += f' ^{block}'
    if not mark[-1:].isspace():
        mark += ' '
    return [mark + first, *(indent + ln for ln in rest)]


def _end(lane):
    return lane['cards'][-1]['end'] if lane['cards'] else lane['head'] + 1


def _find(lanes, lane, text):
    for i, found in enumerate(lanes):
        if found['title'] == lane:
            for card in found['cards']:
                if card['text'] == text:
                    return i, card
    return None, None


def _marked(card, done):
    if card['check'] is None:
        return card['mark']
    return card['mark'].replace(f'[{card["check"]}]', f'[{"x" if done else " "}]', 1)


def replace(text, lane, old, new):
    lines, lanes = text.split('\n'), parse(text)
    _, card = _find(lanes, lane, old)
    if card is None:
        return None
    lines[card['start']:card['end']] = _lines(card['mark'], new, card['block'], _indent(lines, lanes))
    return '\n'.join(lines)


def move(text, lane, old, target):
    lines, lanes = text.split('\n'), parse(text)
    source, card = _find(lanes, lane, old)
    if card is None or not 0 <= target < len(lanes):
        return None
    if target == source:
        return text
    dest = lanes[target]
    mark = card['mark']
    if dest['complete'] or lanes[source]['complete']:
        mark = _marked(card, dest['complete'])
    moved = _lines(mark, card['text'], card['block'], _indent(lines, lanes))
    at = _end(dest)
    if at >= card['end']:
        at -= card['end'] - card['start']
    del lines[card['start']:card['end']]
    lines[at:at] = moved
    return '\n'.join(lines)


def add(text, lane, new):
    lines, lanes = text.split('\n'), parse(text)
    dest = next((found for found in lanes if found['title'] == lane), None)
    if dest is None or not new.strip():
        return None
    at = _end(dest)
    lines[at:at] = _lines('- [x] ' if dest['complete'] else '- [ ] ', new, None, _indent(lines, lanes))
    return '\n'.join(lines)
