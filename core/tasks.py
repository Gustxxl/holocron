import re
from datetime import datetime

_TAG = re.compile(r'(?<!\S)#(\S+)')
_PLACE = re.compile(r'(?<!\S)@(\S+)')


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


def parse_add(text, lists, default, points=None):
    tags, places = _TAG.findall(text), _PLACE.findall(text)
    title = ' '.join(_PLACE.sub(' ', _TAG.sub(' ', text)).split())
    if not title:
        return None, 'Type the reminder text'
    if len(tags) > 1:
        return None, 'Use one #list'
    if len(places) > 1:
        return None, 'Use one @waypoint'
    place = (points or {}).get(places[0].lower()) if places else None
    if places and place is None:
        return None, f'No waypoint @{places[0]}'
    list_id, problem = _pick_list(tags[0] if tags else None, lists, default)
    if problem:
        return None, problem
    return {'title': title, 'list': list_id, 'place': place}, None


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


def _pick_list(tag, lists, default):
    if tag is None:
        return (default, None) if default else (None, 'Choose lists in settings')
    key = _key(tag)
    exact = [l for l in lists if _key(l['title']) == key]
    found = exact or [l for l in lists if key and _key(l['title']).startswith(key)]
    if not found:
        return None, f'No list #{tag}'
    if len(found) > 1:
        return None, f'#{tag} matches several lists'
    return found[0]['id'], None


def _key(text):
    return ''.join(ch for ch in text.lower() if ch.isalnum())


def _order(task):
    due = task['due']
    return (due is None, due or datetime.min)
