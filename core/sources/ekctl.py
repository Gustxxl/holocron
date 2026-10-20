from datetime import date, datetime, timedelta, timezone
from core import sources, system
from . import cli, macos

NAME = 'Calendar'
KEY = 'ekctl'
KIND = 'events'
SETUP = 'macos'
PROGRAM = 'ekctl'
REPO = 'schappim/ekctl'
TAP = 'schappim/ekctl/ekctl'
MACOS = 13
ABOUT = 'Apple Calendar events'
LISTS = 'calendars'
PRIVACY = 'Calendars'
PRIVACY_URL = 'x-apple.systempreferences:com.apple.preference.security?Privacy_Calendars'
HINT = 'No access to Calendar. Open settings (s) > Calendar'
DAYS = 7
DENIED = 2
SHOWN = 2
AHEAD = 2

supported = macos.supported


def status():
    return macos.status(PROGRAM, MACOS, authorized)


def available():
    return system.IS_MACOS and cli.available(PROGRAM)


def authorized():
    return cli.run_code(PROGRAM, 'list', 'calendars') not in (None, DENIED)


def authorize():
    cli.run_code(PROGRAM, 'list', 'calendars', timeout=120)
    return authorized()


def lists():
    return parse_lists(cli.run_json(PROGRAM, 'list', 'calendars'))


def items():
    known = {l['id'] for l in lists() or []}
    chosen = [i for i in sources.selected(KEY) if i in known]
    if not chosen:
        return []
    start = datetime.combine(date.today(), datetime.min.time())
    end = start + timedelta(days=max(DAYS, sources.option(KEY, 'ahead', AHEAD)))
    return parse_items(cli.run_json(PROGRAM, 'list', 'events', '--calendar', ','.join(chosen),
                                    '--from', _stamp(start), '--to', _stamp(end)))


def add(title, list_id, start, end):
    return cli.run_ok(PROGRAM, 'add', 'event', '--calendar', list_id, '--title', title,
                      '--start', _stamp(start), '--end', _stamp(end))


def parse_lists(data):
    found = data.get('calendars') if isinstance(data, dict) else None
    if not isinstance(found, list):
        return None
    return [{'id': d['id'], 'title': d['title']} for d in found
            if isinstance(d, dict) and d.get('type', 'event') == 'event'
            and isinstance(d.get('id'), str) and isinstance(d.get('title'), str)]


def parse_items(data):
    found = data.get('events') if isinstance(data, dict) else None
    if not isinstance(found, list):
        return None
    return [e for e in map(_event, found) if e]


def _stamp(moment):
    return moment.astimezone(timezone.utc).strftime('%Y-%m-%dT%H:%M:%SZ')


def _event(raw):
    if not isinstance(raw, dict) or not isinstance(raw.get('id'), str):
        return None
    start = cli.parse_time(raw.get('startDate'))
    if start is None:
        return None
    calendar = raw.get('calendar') if isinstance(raw.get('calendar'), dict) else {}
    return {
        'id': raw['id'],
        'title': str(raw.get('title') or '').strip() or '(untitled)',
        'start': start,
        'end': cli.parse_time(raw.get('endDate')) or start,
        'all_day': raw.get('allDay') is True,
        'list': calendar.get('id'),
        'list_name': str(calendar.get('title') or '').strip(),
        'place': str(raw.get('location') or '').strip(),
        'notes': str(raw.get('notes') or '').strip(),
        'url': str(raw.get('url') or '').strip(),
        'invitees': ' '.join(map(str, raw['attendees'])) if isinstance(raw.get('attendees'), list) else '',
    }
