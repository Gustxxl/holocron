import re
from datetime import date, datetime, timedelta
from core import dates, tasks

LENGTH = timedelta(hours=1)
_WHEN = re.compile(r'\d{1,2}:\d{2}(?:[-–]\d{1,2}:\d{2})?')
_LINK = re.compile(r'https?://[^\s<>"\']+')
_MEETINGS = ('zoom.us', 'meet.google.com', 'teams.microsoft.com', 'teams.live.com',
             'webex.com', 'whereby.com', 'meet.jit.si', 'telemost')


def upcoming(items, selected, now):
    found = [e for e in items if e['list'] in selected and _left(e, now)]
    return sorted(found, key=lambda e: (e['start'], e['title']))


def by_day(items, now):
    days = {}
    for event in items:
        days.setdefault(max(event['start'].date(), now.date()), []).append(event)
    return list(days.items())


def meeting(event):
    return next((u for u in _links(event) if any(host in u for host in _MEETINGS)), '')


def link(event):
    found = _links(event)
    return meeting(event) or (found[0] if found else '')


def _links(event):
    fields = ('url', 'place', 'notes', 'invitees')
    text = ' '.join(event.get(f) or '' for f in fields)
    return [u.rstrip('.,;)>') for u in _LINK.findall(text)]


def parse_add(text, lists, default, today=None):
    today = today or date.today()
    tags, text = tasks.split_tags(text, lists)
    day, when, words = None, None, []
    for word in text.split():
        if when is None and _WHEN.fullmatch(word):
            when = word
        elif day is None and dates.parse_date(word, today):
            day = dates.parse_date(word, today)
        else:
            words.append(word)
    if not words:
        return None, 'Type the event title'
    if len(tags) > 1:
        return None, 'Use one #calendar'
    if when is None:
        return None, 'Add a time, e.g. 14:30 or 14:30-15:00'
    span = _span(when, day or today)
    if span is None:
        return None, f'No such time: {when}'
    list_id, problem = tasks.pick_list(tags[0] if tags else None, lists, default)
    if problem:
        return None, problem
    return {'title': ' '.join(words), 'list': list_id, 'start': span[0], 'end': span[1]}, None


def _span(when, day):
    period = dates.parse_period(when)
    if period:
        return dates.period_on(day, *period)
    start = dates.parse_time(when)
    if start is None:
        return None
    begin = datetime.combine(day, dates.to_time(start))
    return begin, begin + LENGTH


def _left(event, now):
    if event['end'] > event['start']:
        return event['end'] > now
    return event['start'].date() >= now.date()
