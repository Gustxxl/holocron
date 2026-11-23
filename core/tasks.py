import re
from datetime import date, datetime
from core import dates

_TAG = re.compile(r'(?<!\S)#(\S+)')
_PLACE = re.compile(r'(?<!\S)@(\S+)')


def is_overdue(task, now=None):
    now = now or datetime.now()
    due = task.get('due')
    if due is None:
        return False
    return due.date() < now.date() if task.get('all_day') else due < now


def since(now, shift_start=None):
    start = datetime.combine(now.date(), datetime.min.time())
    return min(start, shift_start) if shift_start else start


def done_today(items, selected, start):
    found = [t for t in items if t['done'] and t['list'] in selected and t.get('finished') and t['finished'] >= start]
    return sorted(found, key=lambda t: t['finished'])


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


def split_tags(text, lists):
    tags = []
    for title in sorted((l['title'] for l in lists if l['title'].strip()), key=len, reverse=True):
        found = re.compile(rf'(?<!\S)#{re.escape(title)}(?!\S)', re.IGNORECASE)
        tags += [title] * len(found.findall(text))
        text = found.sub(' ', text)
    return tags + _TAG.findall(text), _TAG.sub(' ', text)


def parse_add(text, lists, default, points=None, today=None, now=None):
    now = now or datetime.now()
    today = today or now.date()
    tags, text = split_tags(text, lists)
    places = _PLACE.findall(text)
    day, when, words = dates.split_when(_PLACE.sub(' ', text), today)
    if not words:
        return None, 'Type the reminder text'
    if len(tags) > 1:
        return None, 'Use one #list'
    if len(places) > 1:
        return None, 'Use one @waypoint'
    place = (points or {}).get(places[0].lower()) if places else None
    if places and place is None:
        return None, f'No waypoint @{places[0]}'
    due, problem = _due(day, when, today, now)
    if problem:
        return None, problem
    list_id, problem = pick_list(tags[0] if tags else None, lists, default)
    if problem:
        return None, problem
    return {'title': ' '.join(words), 'list': list_id, 'place': place, 'due': due}, None


def first_line(task, today):
    parts = [task['title']]
    due = task.get('due')
    if due is not None:
        parts.append(f'{due:%d-%m}' if due.year == today.year else f'{due:%d-%m-%Y}')
        if not task.get('all_day'):
            parts.append(f'{due:%H:%M}')
    if task.get('list_name'):
        parts.append(f'#{task["list_name"]}')
    return ' '.join(parts)


def to_text(task, today=None):
    notes = task.get('notes') or ''
    return first_line(task, today or date.today()) + (f'\n\n{notes}' if notes else '')


def changes(task, text, lists, today=None, now=None):
    now = now or datetime.now()
    today = today or now.date()
    lines = text.strip().splitlines()
    line = lines[0].strip() if lines else ''
    if not line:
        return None, 'Empty text — edit cancelled'
    notes = '\n'.join(lines[1:]).strip()
    found = {}
    if line != first_line(task, today):
        draft, problem = parse_add(line, lists, task.get('list'), today=today, now=now)
        if problem:
            return None, problem
        if draft['title'] != task['title']:
            found['title'] = draft['title']
        if not _same_due(task, draft['due']):
            found['due'] = draft['due']
            found.update(_alarm(task, draft['due']))
        if draft['list'] != task.get('list'):
            found['list'] = draft['list']
    if notes != (task.get('notes') or ''):
        found['notes'] = notes
    return found, None


def apply(task, found, lists):
    for key in ('title', 'notes', 'alarm'):
        if key in found:
            task[key] = found[key]
    if 'due' in found:
        due = found['due']
        task['all_day'] = due is not None and not isinstance(due, datetime)
        task['due'] = datetime.combine(due, datetime.min.time()) if task['all_day'] else due
    if 'list' in found:
        task['list'] = found['list']
        task['list_name'] = next((l['title'] for l in lists if l['id'] == found['list']), '')


def pick_list(tag, lists, default, kind='list'):
    if tag is None:
        return (default, None) if default else (None, f'Choose {kind}s in settings')
    key = _key(tag)
    exact = [l for l in lists if _key(l['title']) == key]
    found = exact or [l for l in lists if key and _key(l['title']).startswith(key)]
    if not found:
        return None, f'No {kind} #{tag}'
    if len(found) > 1:
        return None, f'#{tag} matches several {kind}s'
    return found[0]['id'], None


def _due(day, when, today, now):
    if when is None:
        return day, None
    later = dates.after(when, now)
    if later:
        return (None, dates.BOTH) if day else (later, None)
    if dates.parse_period(when):
        return None, 'Use one time, e.g. 22:05'
    start = dates.parse_time(when)
    if start is None:
        return None, f'No such time: {when}'
    return datetime.combine(day or today, dates.to_time(start)), None


def _same_due(task, due):
    old = task.get('due')
    if old is None or due is None:
        return old is None and due is None
    if task.get('all_day'):
        return not isinstance(due, datetime) and old.date() == due
    return isinstance(due, datetime) and old.replace(second=0, microsecond=0) == due


def _alarm(task, due):
    old, alarm = task.get('due'), task.get('alarm')
    timed = old is not None and not task.get('all_day')
    if isinstance(due, datetime):
        if timed and alarm:
            return {'alarm': due - (old - alarm)}
        return {} if timed else {'alarm': due}
    return {'alarm': None} if timed and alarm else {}


def _key(text):
    return ''.join(ch for ch in text.lower() if ch.isalnum())


def _order(task):
    due = task['due']
    return (due is None, due or datetime.min)
