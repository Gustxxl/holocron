import json
import re
import shutil
import time
import unicodedata
import urllib.request
import urllib.error
import threading

from core import search
from core.settings import KEEPER_LOCAL_URL, keeper_server, keeper_model

RECOMMENDED = 'qwen2.5:7b'
TOP_K = 8
RECORDS = 5
SNIPPET = 1000
FOCUS = 6000
COMMON_SHARE = 0.25
MAX_LINES = 150
MAX_RECORD = 8000
MAX_REPLY = 1500
MAX_QUOTES = 4
MAX_LINKS = 3
HISTORY_TURNS = 6
HISTORY_REPLY = 600
CHAT_TEMPERATURE = 0.3
CACHE_SECONDS = 300
PROBE_TIMEOUT = 2


_PLAN_PROMPT = (
    'You prepare an archive lookup for Keeper, the assistant of a personal archive of work notes. '
    'You get the conversation so far, the records already shown, and the last message. '
    'Return strict JSON: {"terms": ["..."], "records": [numbers]}. '
    '"terms" are 0 to 6 short search terms needed to answer the last message: subjects, document names, '
    'statuses, error text, codes, numbers, dates. '
    'Replace references like "it", "that error", "the second one" with the actual subject from the conversation. '
    'Use an empty list for greetings, small talk, or when the answer is already in the shown records. '
    '"records" are numbers of shown records the last message refers to, otherwise an empty list. '
    'Keep every term in the same language and spelling as the conversation. Never translate. '
    'Example: "how do I refund order 12345?" -> {"terms": ["refund", "order", "12345"], "records": []}'
)

_REPLY_PROMPT = (
    'You are Keeper, the archivist of Holocron, a private archive of the user\'s work notes. '
    'Manner: quiet, restrained and exact, like an old imperial archivist. '
    'No greetings, no compliments, no enthusiasm, no exclamation marks, no emoji. '
    'Never mention being an AI or a model. '
    'Reply only in the language of the user\'s last message. '
    'You may get numbered records from the archive. Use them when they help: answer from them, retell them, '
    'compare them, point to similar cases, or rewrite their text when asked. Refer to records by number, like [2]. '
    'Never invent numbers, codes, dates, names or links that are not in the records or the conversation. '
    'If no record fits, say so in one short sentence and still help: ask what is meant, '
    'or answer from general knowledge. If the message is unclear, ask one short question. '
    'Keep replies short, up to five sentences, unless the user asks for a rewrite or details. '
    'Records may list their links as L1, L2 and so on. When the answer depends on a link, '
    'such as the instruction, ticket or document the record points to, put its numbers in "links", '
    'most important first, at most three. Never copy links into "reply". '
    'Return strict JSON: {"reply": "text", "used": [numbers of records you relied on], '
    '"quotes": ["exact lines copied from those records"], "links": [link numbers]}. '
    'Examples: "hi" -> {"reply": "Holocron is open.", "used": [], "quotes": [], "links": []} '
    '"how are you?" -> {"reply": "Functional. The archive is in order.", "used": [], "quotes": [], "links": []}'
)

_WORD_RE = re.compile(r'[\w-]+')
_URL_RE = re.compile(r'https?://\S+')
_MD_LINK_RE = re.compile(r'\[([^\]]*)\]\((https?://[^)\s]+)\)')
_REF_RE = re.compile(r'\[\d+\]')

_active = {'conn': None, 'at': 0.0}


class KeeperOffline(Exception):
    pass


def connections():
    out = []
    server = keeper_server()
    if server:
        out.append({'slot': 'server', 'url': server, 'model': keeper_model('server')})
    out.append({'slot': 'local', 'url': KEEPER_LOCAL_URL, 'model': keeper_model('local')})
    return out


def connection(slot):
    return next((c for c in connections() if c['slot'] == slot), None)


def has_server():
    return bool(keeper_server())


def _open(conn, path, payload=None, timeout=120):
    data = json.dumps(payload).encode('utf-8') if payload is not None else None
    req = urllib.request.Request(conn['url'] + path, data=data,
                                 headers={'Content-Type': 'application/json'})
    return urllib.request.urlopen(req, timeout=timeout)


def _get_json(conn, path, payload=None, timeout=120):
    with _open(conn, path, payload, timeout) as resp:
        return json.loads(resp.read().decode('utf-8'))


def _list_models(conn):
    try:
        data = _get_json(conn, '/api/tags', timeout=PROBE_TIMEOUT)
        return sorted(m['name'] for m in data.get('models', []) if m.get('name'))
    except (urllib.error.URLError, OSError, ValueError, AttributeError, TypeError):
        return None


def status(conn):
    found = _list_models(conn)
    if found is None:
        if conn['slot'] == 'local':
            return ('stopped' if shutil.which('ollama') else 'missing'), []
        return 'off', []
    if not found:
        return 'no_models', found
    if not conn['model']:
        return 'no_model', found
    if conn['model'] not in found:
        return 'model_missing', found
    return 'ready', found


def reset():
    _active.update(conn=None, at=0.0)


def cached():
    return bool(_active['at']) and time.monotonic() - _active['at'] < CACHE_SECONDS


def _probe(conns):
    states = [None] * len(conns)

    def check(i, conn):
        states[i] = status(conn)[0]

    threads = [threading.Thread(target=check, args=(i, c), daemon=True) for i, c in enumerate(conns)]
    for t in threads:
        t.start()
    deadline = time.monotonic() + PROBE_TIMEOUT
    for t in threads:
        t.join(max(0.0, deadline - time.monotonic()))
    return next((c for c, s in zip(conns, states) if s == 'ready'), None)


def configured():
    return [c for c in connections() if c.get('model')]


def active(refresh=False):
    if not refresh and cached():
        return _active['conn']
    conns = configured()
    chosen = _probe(conns) if conns else None
    _active.update(conn=chosen, at=time.monotonic())
    return chosen


def current_slot():
    conn = _active['conn']
    return conn['slot'] if conn else None


def pull(conn, name, progress):
    try:
        with _open(conn, '/api/pull', {'model': name, 'name': name, 'stream': True}, 600) as resp:
            for line in resp:
                if not line.strip():
                    continue
                data = json.loads(line)
                if data.get('error'):
                    raise KeeperOffline(data['error'])
                progress(data.get('status', ''), data.get('completed'), data.get('total'))
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise KeeperOffline(str(e))


def _parse_json(text):
    if not isinstance(text, str):
        return {}
    start, end = text.find('{'), text.rfind('}')
    if start == -1 or end <= start:
        return {}
    try:
        result = json.loads(text[start:end + 1])
    except ValueError:
        return {}
    return result if isinstance(result, dict) else {}


def _chat_with(conn, system, user, history, temperature):
    messages = [{'role': 'system', 'content': system}]
    messages += history or []
    messages.append({'role': 'user', 'content': user})
    payload = {
        'model': conn['model'],
        'messages': messages,
        'stream': False,
        'format': 'json',
        'options': {'temperature': temperature, 'num_ctx': 8192},
    }
    try:
        data = _get_json(conn, '/api/chat', payload)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise KeeperOffline(str(e))
    try:
        return _parse_json(data['message']['content'])
    except (KeyError, TypeError):
        return {}


def _chat(system, user, history=None, temperature=0):
    conn = active()
    if conn is None:
        raise KeeperOffline('no connection')
    try:
        return _chat_with(conn, system, user, history, temperature)
    except KeeperOffline:
        retry = active(refresh=True)
        if retry is None or retry['slot'] == conn['slot']:
            raise
        return _chat_with(retry, system, user, history, temperature)


def _norm(word):
    return word.strip().lower().replace('ё', 'е')


def _flat(text):
    return ' '.join(_WORD_RE.findall(_norm(text)))


def _numbers(values, limit):
    out = []
    for n in values if isinstance(values, list) else []:
        try:
            n = int(n)
        except (TypeError, ValueError):
            continue
        if 1 <= n <= limit and n not in out:
            out.append(n)
    return out


def _clean_terms(terms):
    if not isinstance(terms, list):
        return []
    out = []
    for t in terms:
        t = _norm(str(t))
        if len(t) >= 3 and t not in out:
            out.append(t)
    return out[:6]


def _grounded(terms, context):
    words = _WORD_RE.findall(_norm(context))
    out = []
    for t in terms:
        parts = _WORD_RE.findall(t)
        if parts and all(
            any(
                w == q
                or (len(w) >= 3 and len(q) >= 3 and w[:3] == q[:3])
                or (w.isdigit() and q.isdigit() and w == q)
            for q in words)
            for w in parts
        ):
            out.append(t)
    return out


def _common_words(cases):
    if not cases:
        return set()
    counts = {}
    for c in cases:
        for w in set(_WORD_RE.findall(_norm(c['text']))):
            counts[w] = counts.get(w, 0) + 1
    limit = max(2, len(cases) * COMMON_SHARE)
    return {w for w, n in counts.items() if n > limit}


def _plain_terms(question, cases):
    common = _common_words(cases)
    out = []
    for w in _WORD_RE.findall(_norm(question)):
        has_digit = any(ch.isdigit() for ch in w)
        if (len(w) >= 3 or has_digit) and w not in common and w not in out:
            out.append(w)
    return out[:8]


def _candidates(cases, terms):
    total = {}
    queries = [(2.0, ' '.join(terms))] + [(1.0, t) for t in terms]
    for weight, q in queries:
        if len(q) < 3:
            continue
        for score, c in search.search(cases, q):
            s, _ = total.get(id(c), (0.0, c))
            total[id(c)] = (s + weight * score, c)
    ranked = sorted(total.values(), key=lambda t: -t[0])
    return [c for _, c in ranked[:TOP_K]]


def _named(question, cases):
    q = _norm(question)
    return [c for c in cases
            if len(c.get('filename', '')) >= 4 and _norm(c['filename']) in q]


def _script(text):
    counts = {}
    for ch in text:
        if not ch.isalpha():
            continue
        try:
            name = unicodedata.name(ch).split()[0]
        except ValueError:
            continue
        counts[name] = counts.get(name, 0) + 1
    return max(counts, key=counts.get) if counts else None


def _same_script(text, question):
    expected = _script(question)
    return expected is None or _script(text) == expected


def _foreign_numbers(text, source):
    known = set(re.findall(r'\d+', source))
    return [n for n in re.findall(r'\d+', text) if n not in known]


def _foreign_links(text, source):
    return [u for u in _URL_RE.findall(text) if u.rstrip('.,;)') not in source]


def _record_lines(text):
    out, size = [], 0
    for ln in text.splitlines():
        ln = ln.strip()
        if not ln:
            continue
        room = MAX_RECORD - size
        if room <= 0 or len(out) >= MAX_LINES:
            break
        out.append(ln[:room])
        size += len(out[-1])
    return out


def title(case):
    name = case.get('filename')
    if name:
        return name
    return next((ln.strip() for ln in case['text'].splitlines() if ln.strip()), '')[:80]


def _record(case, limit):
    name = case.get('filename', '')
    body = '\n'.join(_record_lines(case['text']))[:limit]
    return f'{name}\n{body}' if name else body


def _transcript(history):
    out = []
    for m in history or []:
        content = m['content']
        if m['role'] == 'assistant':
            content = _parse_json(content).get('reply', content)
        out.append(f"{'User' if m['role'] == 'user' else 'Keeper'}: {content}")
    return '\n'.join(out)


def history(turns):
    out = []
    for t in [t for t in turns if t.get('reply')][-HISTORY_TURNS:]:
        shown = '; '.join(f'[{n}] {title(c)}' for n, c in enumerate(t.get('sources', []), t.get('start', 1)))
        text = t['reply'][:HISTORY_REPLY] + (f'\nRecords shown: {shown}' if shown else '')
        text += ''.join(f'\nLink given: {url}' for url, _ in t.get('links', []))
        out.append({'role': 'user', 'content': t['question']})
        out.append({'role': 'assistant', 'content': json.dumps({'reply': text}, ensure_ascii=False)})
    return out


def _plan(message, past, records):
    talk = _transcript(past)
    shown = '\n'.join(f'[{n}] {title(c)}' for n, c in enumerate(records, 1))
    user = (f'Conversation:\n{talk}\n\n' if talk else '') + \
           (f'Shown records:\n{shown}\n\n' if shown else '') + f'Last message: {message}'
    data = _chat(_PLAN_PROMPT, user)
    terms = _grounded(_clean_terms(data.get('terms')), message + ' ' + talk)
    return terms, _numbers(data.get('records'), len(records))


def _gather(cases, message, terms, refs, records, focus):
    picked = []
    for c in [focus] if focus else []:
        picked.append(c)
    for c in [records[n - 1] for n in refs] + _named(message, cases) + (_candidates(cases, terms) if terms else []):
        if all(c is not p for p in picked):
            picked.append(c)
    return picked[:RECORDS + (1 if focus else 0)]


def _links(case):
    text = case['text']
    labels = {url: label.strip() for label, url in _MD_LINK_RE.findall(text)}
    out = []
    for raw in _URL_RE.findall(text):
        url = raw.rstrip('.,;:)]>|"\'')
        if all(url != u for u, _ in out):
            out.append((url, labels.get(url, '')))
    return out


def _ask(message, past, picked, focus, temperature):
    blocks, links = [], []
    for i, c in enumerate(picked, 1):
        block = f'[{i}] {_record(c, FOCUS if c is focus else SNIPPET)}'
        own = _links(c)
        if own:
            rows = [f'L{len(links) + n}: {label} {url}'.replace(':  ', ': ')
                    for n, (url, label) in enumerate(own, 1)]
            block += '\nLinks:\n' + '\n'.join(rows)
            links += own
        blocks.append(block)
    user = 'Records:\n' + '\n\n'.join(blocks) + f'\n\nMessage: {message}' if blocks else message
    return _chat(_REPLY_PROMPT, user, past, temperature), links


def _quotes(values, used, reply):
    sources = [_flat(c['text']) for c in used]
    said = _flat(reply)
    out = []
    for q in values if isinstance(values, list) else []:
        q = ' '.join(str(q).split())
        f = _flat(q)
        if len(f) >= 8 and f != said and any(f in s for s in sources) and q not in out:
            out.append(q)
    return out[:MAX_QUOTES]


def _check(data, message, past, picked, links):
    reply = str(data.get('reply') or '').strip()
    if not reply or len(reply) > MAX_REPLY or not _same_script(reply, message):
        return None
    if any(unicodedata.category(ch) == 'So' for ch in reply):
        return None
    used = [picked[n - 1] for n in _numbers(data.get('used'), len(picked))]
    known = ' '.join(title(c) + ' ' + c['text'] for c in used) + ' ' + message + ' ' + _transcript(past)
    bare = _REF_RE.sub('', reply)
    if used and _foreign_numbers(bare, known):
        return None
    if _foreign_links(bare, known):
        return None
    chosen = [links[n - 1] for n in _numbers(data.get('links'), len(links))][:MAX_LINKS]
    return {'reply': reply, 'used': used, 'quotes': _quotes(data.get('quotes'), used, reply), 'links': chosen}


def reply(message, past, cases, records=(), focus=None, progress=None):
    step = progress or (lambda _: None)
    records = list(records)
    out = {'reply': '', 'quotes': [], 'sources': [], 'cited': 0, 'archive': False,
           'lookup': False, 'terms': '', 'online': False}

    terms, refs, online = [], [], active() is not None
    if online:
        try:
            terms, refs = _plan(message, past, records)
        except KeeperOffline:
            online = False

    if not online:
        terms = _plain_terms(message, cases)
        found = _named(message, cases)
        found += [c for c in (_candidates(cases, terms) if terms else []) if all(c is not f for f in found)]
        out.update(terms=' '.join(terms), sources=found[:RECORDS], lookup=True)
        return out

    if terms:
        step('searching')
    picked = _gather(cases, message, terms, refs, records, focus)
    out.update(online=True, terms=' '.join(terms), lookup=bool(terms or refs))
    if picked:
        step('reading')

    checked = None
    for temperature in (CHAT_TEMPERATURE, 0):
        try:
            data, links = _ask(message, past, picked, focus, temperature)
            checked = _check(data, message, past, picked, links)
        except KeeperOffline:
            out['online'] = False
            break
        if checked:
            break

    rest = [c for c in picked if c is not focus]
    if checked:
        used = [c for c in checked['used'] if c is not focus]
        others = [c for c in rest if all(c is not u for u in used)] if used else []
        out.update(reply=checked['reply'], quotes=checked['quotes'], sources=(used + others)[:RECORDS],
            cited=len(used), archive=bool(checked['used']), links=checked['links'])
    else:
        out['sources'] = rest[:RECORDS]
    return out
