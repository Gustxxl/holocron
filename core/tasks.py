import re
from datetime import datetime

_TAG = re.compile(r'(?<!\S)#(\S+)')


def is_overdue(task, now=None):
    now = now or datetime.now()
    due = task.get('due')
    if due is None:
        return False
    return due.date() < now.date() if task.get('all_day') else due < now


def group(items, lists, selected):
    by_list = {}
    for task in items:
        if not task['done']:
            by_list.setdefault(task['list'], []).append(task)
    return [(l['title'], sorted(by_list.get(l['id'], []), key=_order))
            for l in lists if l['id'] in selected]


def numbered(groups):
    return [task for _, items in groups for task in items]


def upcoming(items, selected, limit=3):
    rank = {list_id: i for i, list_id in enumerate(selected)}
    found = [t for t in items if not t['done'] and t['list'] in rank]
    found.sort(key=lambda t: (*_order(t), rank[t['list']]))
    return found[:limit], max(0, len(found) - limit)


def parse_add(text, lists, default):
    tags = _TAG.findall(text)
    title = ' '.join(_TAG.sub(' ', text).split())
    if not title:
        return None, None, 'Type the reminder text'
    if len(tags) > 1:
        return None, None, 'Use one #list'
    if not tags:
        if default is None:
            return None, None, 'Choose lists in settings'
        return title, default, None
    key = _key(tags[0])
    exact = [l for l in lists if _key(l['title']) == key]
    found = exact or [l for l in lists if key and _key(l['title']).startswith(key)]
    if not found:
        return None, None, f'No list #{tags[0]}'
    if len(found) > 1:
        return None, None, f'#{tags[0]} matches several lists'
    return title, found[0]['id'], None


def to_text(task):
    notes = task.get('notes') or ''
    return task['title'] + (f'\n\n{notes}' if notes else '')


def changes(task, text):
    lines = text.strip().splitlines()
    title = lines[0].strip() if lines else ''
    if not title:
        return None
    notes = '\n'.join(lines[1:]).strip()
    found = {}
    if title != task['title']:
        found['title'] = title
    if notes != (task.get('notes') or ''):
        found['notes'] = notes
    return found


def _key(text):
    return ''.join(ch for ch in text.lower() if ch.isalnum())


def _order(task):
    due = task['due']
    return (due is None, due or datetime.min)
