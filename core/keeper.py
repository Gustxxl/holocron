import json
import re
import shutil
import time
import unicodedata
import urllib.request
import urllib.error

from core import search
from core.settings import KEEPER_LOCAL_URL, keeper_server, keeper_model

RECOMMENDED = 'qwen2.5:7b'
TOP_K = 8
SNIPPET = 600
COMMON_SHARE = 0.25
MAX_LINES = 40
MAX_QUOTES = 12
MAX_SUMMARY = 400
MAX_REPLY = 300
GROUNDING_MIN = 0.6
CHAT_TEMPERATURE = 0.3
CACHE_SECONDS = 30
PROBE_TIMEOUT = 2


_ROUTE_PROMPT = (
    'You route messages for Keeper, the assistant of a personal archive of work notes. '
    'Return strict JSON: {"intent": "archive" or "chat", "terms": ["...", "..."]}. '
    'Use "archive" when the user asks about work, procedures, documents, errors, codes, '
    'numbers or anything that could be written in their notes. '
    'Dates, day names, and date ranges always mean "archive". '
    'Use "chat" for greetings, small talk, feelings, life and general conversation. '
    'For "archive" give 2 to 6 short search terms: subjects, document names, statuses, '
    'codes, numbers, dates. '
    'A date like "02 Jun 2026" should produce terms ["02", "Jun", "2026"]. '
    'Skip requests, pronouns and generic words. '
    'Keep every term in the same language and spelling as the message. Never translate. '
    'For "chat" return an empty terms list. '
    'Example: "how do I refund a customer for order 12345?" -> '
    '{"intent": "archive", "terms": ["refund", "customer", "order", "12345"]}'
)

_PICK_PROMPT = (
    'You help find a record in a personal archive. You get a question and numbered records, '
    'each may start with its title. '
    'Pick the records that answer the question, describe the same situation, '
    'or whose title matches a date, name or code from the question. '
    'If none fit, return an empty list. Do not guess. '
    'Answer in strict JSON: {"match": [numbers]}. At most 3 numbers, best first.'
)

_ANSWER_PROMPT = (
    'You are Keeper, the archivist of Holocron. '
    'You get a question and one record: an optional title and numbered lines. '
    'Return strict JSON: {"lines": [numbers], "summary": "text"}. '
    '"lines" are the line numbers that answer the question. '
    'If the question asks what the record contains or asks to recall it, '
    'pick its key lines and summarize them. '
    '"summary" states the answer in one or two plain, exact sentences, using only this record. '
    'No greetings, no pleasantries, no advice beyond the record. '
    'Write the summary in the same language as the question. No links. '
    'If the record does not answer the question, return {"lines": [], "summary": ""}.'
)

_CHAT_PROMPT = (
    'You are Keeper, the archivist of Holocron, a private archive. '
    'Your manner is quiet, restrained and exact, like an old imperial archivist. '
    'Speak in short plain statements, one or two sentences. '
    'No greetings, no compliments, no enthusiasm, no jokes, no metaphors, '
    'no quotes or sayings, no exclamation marks, no emoji. '
    'You do not serve or flatter the user. You value precision over warmth. '
    'Do not ask questions back unless something essential is missing. '
    'Reply only in the language of the user\'s last message. '
    'Never mention being an AI or a model. Do not claim knowledge of the archive. '
    'Return strict JSON: {"reply": "text"}. '
    'Examples: '
    '"hi" -> {"reply": "Holocron is open."} '
    '"how are you?" -> {"reply": "Functional. The archive is in order."} '
    '"tell me about life" -> {"reply": "Life is not kept here. Only what you chose to record."}'
)

_WORD_RE = re.compile(r'[\w-]+')
_URL_RE = re.compile(r'https?://\S+')

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


def active(refresh=False):
    now = time.monotonic()
    if not refresh and _active['at'] and now - _active['at'] < CACHE_SECONDS:
        return _active['conn']
    chosen = None
    for conn in connections():
        if status(conn)[0] == 'ready':
            chosen = conn
            break
    _active.update(conn=chosen, at=now)
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


def _grounded(terms, question):
    q_words = _WORD_RE.findall(_norm(question))
    out = []
    for t in terms:
        parts = _WORD_RE.findall(t)
        if parts and all(
            any(
                w == q
                or (len(w) >= 3 and len(q) >= 3 and w[:3] == q[:3])
                or (w.isdigit() and q.isdigit() and w == q)
            for q in q_words)
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


def _pick(question, cands):
    blocks = []
    for i, c in enumerate(cands, 1):
        text = ' '.join(c['text'].split())[:SNIPPET]
        name = c.get('filename', '')
        blocks.append(f'[{i}] {name}: {text}' if name else f'[{i}] {text}')
    user = 'Question: ' + question + '\n\nRecords:\n' + '\n\n'.join(blocks)
    data = _chat(_PICK_PROMPT, user)
    return [cands[n - 1] for n in _numbers(data.get('match'), len(cands))][:3]


def _named(question, cases):
    q = _norm(question)
    return [c for c in cases
            if len(c.get('filename', '')) >= 4 and _norm(c['filename']) in q]


def find(cases, question, terms, online):
    terms = terms or _plain_terms(question, cases)
    similar = _candidates(cases, terms) if terms else []
    named = _named(question, cases)
    picked = []
    if online and similar:
        try:
            picked = _pick(question, similar)
        except KeeperOffline:
            online = False
    picked = (named + [c for c in picked if all(c is not n for n in named)])[:3]
    similar = named + [c for c in similar if all(c is not n for n in named)]
    return {'terms': terms, 'picked': picked, 'similar': similar, 'online': online}


def answer(question, case):
    title = case.get('filename', '')
    lines = [ln.strip() for ln in case['text'].splitlines() if ln.strip()][:MAX_LINES]
    numbered = '\n'.join(f'{i}: {ln}' for i, ln in enumerate(lines, 1))
    header = f'Title: {title}\n' if title else ''
    data = _chat(_ANSWER_PROMPT, f'Question: {question}\n\nRecord:\n{header}{numbered}')
    quotes = [lines[n - 1] for n in sorted(_numbers(data.get('lines'), len(lines)))]
    summary = str(data.get('summary') or '').strip()
    if not _valid_summary(summary, question, title + ' ' + case['text']):
        summary = ''
    return {'summary': summary, 'lines': quotes[:MAX_QUOTES]}


def route(question):
    offline = {'online': False, 'intent': 'archive', 'terms': []}
    if active() is None:
        return offline
    try:
        data = _chat(_ROUTE_PROMPT, question)
    except KeeperOffline:
        return offline
    intent = 'chat' if data.get('intent') == 'chat' else 'archive'
    terms = _grounded(_clean_terms(data.get('terms')), question)
    return {'online': True, 'intent': intent, 'terms': terms}


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


def _grounding(summary, source):
    words = [w for w in _WORD_RE.findall(_norm(summary)) if len(w) >= 5]
    if not words:
        return 0.0
    known = {w[:5] for w in _WORD_RE.findall(_norm(source)) if len(w) >= 5}
    return sum(1 for w in words if w[:5] in known) / len(words)


def _restrained(text, max_sentences):
    if '!' in text:
        return False
    if any(unicodedata.category(ch) == 'So' for ch in text):
        return False
    return len(re.findall(r'[.?…]+(?:\s|$)', text)) <= max_sentences


def _valid_summary(summary, question, record):
    return (
        summary
        and len(summary) <= MAX_SUMMARY
        and not _URL_RE.search(summary)
        and _restrained(summary, 2)
        and _same_script(summary, question)
        and _grounding(summary, record + ' ' + question) >= GROUNDING_MIN
    )


def _valid_reply(reply, question):
    return (
        reply
        and len(reply) <= MAX_REPLY
        and not _URL_RE.search(reply)
        and _restrained(reply, 3)
        and _same_script(reply, question)
    )


def answer(question, case):
    lines = [ln.strip() for ln in case['text'].splitlines() if ln.strip()][:MAX_LINES]
    numbered = '\n'.join(f'{i}: {ln}' for i, ln in enumerate(lines, 1))
    data = _chat(_ANSWER_PROMPT, f'Question: {question}\n\nRecord:\n{numbered}')
    quotes = [lines[n - 1] for n in sorted(_numbers(data.get('lines'), len(lines)))]
    summary = str(data.get('summary') or '').strip()
    if not _valid_summary(summary, question, case['text']):
        summary = ''
    return {'summary': summary, 'lines': quotes[:MAX_QUOTES]}


def chat(question, history=None):
    for _ in range(2):
        data = _chat(_CHAT_PROMPT, question, history, CHAT_TEMPERATURE)
        reply = str(data.get('reply') or '').strip()
        if _valid_reply(reply, question):
            return reply
    return ''
