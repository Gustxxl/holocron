from datetime import datetime


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


def upcoming(items, selected, limit=3):
    rank = {list_id: i for i, list_id in enumerate(selected)}
    found = [t for t in items if not t['done'] and t['list'] in rank]
    found.sort(key=lambda t: (*_order(t), rank[t['list']]))
    return found[:limit], max(0, len(found) - limit)


def _order(task):
    due = task['due']
    return (due is None, due or datetime.min)
