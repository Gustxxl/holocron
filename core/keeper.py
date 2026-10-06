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
GROUNDING_MIN = 0.6
CACHE_SECONDS = 30
PROBE_TIMEOUT = 2

_TERMS_PROMPT = (
    'You extract search terms from a question to search a personal archive of work notes. '
    'Return strict JSON: {"terms": ["...", "..."]}. '
    'Give 2 to 6 short terms: subjects, document names, statuses, codes, numbers. '
    'Skip requests, pronouns and generic words. '
    'Keep every term in the same language and spelling as the question. Never translate. '
    'Example: "how do I refund a customer for order 12345?" -> '
    '{"terms": ["refund", "customer", "order", "12345"]}'
)

_PICK_PROMPT = (
    'You help find a record in a personal archive. You get a question and numbered records. '
    'Pick the records that directly answer the question or describe the same situation. '
    'If none fit, return an empty list. Do not guess. '
    'Answer in strict JSON: {"match": [numbers]}. At most 3 numbers, best first.'
)

_ANSWER_PROMPT = (
    'You are Keeper, the assistant of the Holocron archive. '
    'You get a question and one record split into numbered lines. '
    'Return strict JSON: {"lines": [numbers], "summary": "text"}. '
    '"lines" are the line numbers that answer the question. '
    '"summary" is one or two short sentences that answer the question using only this record. '
    'Write the summary in the same language as the question. '
    'Never add facts that are not in the record. No links. '
    'If the record does not answer the question, return {"lines": [], "summary": ""}.'
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


def _chat_with(conn, system, user):
    payload = {
        'model': conn['model'],
        'messages': [
            {'role': 'system', 'content': system},
            {'role': 'user', 'content': user},
        ],
        'stream': False,
        'format': 'json',
        'options': {'temperature': 0, 'num_ctx': 8192},
    }
    try:
        data = _get_json(conn, '/api/chat', payload)
    except (urllib.error.URLError, OSError, ValueError) as e:
        raise KeeperOffline(str(e))
    try:
        return _parse_json(data['message']['content'])
    except (KeyError, TypeError):
        return {}


def _chat(system, user):
    conn = active()
    if conn is None:
        raise KeeperOffline('no connection')
    try:
        return _chat_with(conn, system, user)
    except KeeperOffline:
        retry = active(refresh=True)
        if retry is None or retry['slot'] == conn['slot']:
            raise
        return _chat_with(retry, system, user)


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


def _llm_terms(question):
    terms = _chat(_TERMS_PROMPT, question).get('terms', [])
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
            any(w == q or (len(w) >= 4 and len(q) >= 4 and w[:4] == q[:4]) for q in q_words)
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
        if (len(w) > 3 or has_digit) and w not in common and w not in out:
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
        blocks.append(f'[{i}] {text}')
    user = 'Question: ' + question + '\n\nRecords:\n' + '\n\n'.join(blocks)
    data = _chat(_PICK_PROMPT, user)
    return [cands[n - 1] for n in _numbers(data.get('match'), len(cands))][:3]


def ask(cases, question):
    online = active() is not None
    terms = []
    if online:
        try:
            terms = _grounded(_llm_terms(question), question)
        except KeeperOffline:
            online = False
    terms = terms or _plain_terms(question, cases)
    similar = _candidates(cases, terms) if terms else []
    picked = []
    if online and similar:
        try:
            picked = _pick(question, similar)
        except KeeperOffline:
            online = False
    conn = _active['conn'] if online else None
    return {
        'terms': terms,
        'picked': picked,
        'similar': similar,
        'online': online,
        'via': conn['slot'] if conn else None,
    }


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


def _grounding(summary, source):
    words = [w for w in _WORD_RE.findall(_norm(summary)) if len(w) >= 5]
    if not words:
        return 0.0
    known = {w[:5] for w in _WORD_RE.findall(_norm(source)) if len(w) >= 5}
    return sum(1 for w in words if w[:5] in known) / len(words)


def _valid_summary(summary, question, record):
    return (
        summary
        and len(summary) <= MAX_SUMMARY
        and not _URL_RE.search(summary)
        and _script(summary) == _script(question)
        and _grounding(summary, record + ' ' + question) >= GROUNDING_MIN
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
