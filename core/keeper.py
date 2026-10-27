import json
import re
import shutil
import time
import unicodedata
import urllib.request
import urllib.error
import threading
from decimal import Decimal, InvalidOperation

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
MAX_STEPS = 2500
MAX_PARAGRAPHS = 40
MAX_UNITS = 10
LABEL_WORDS = 6
MIN_LABEL = 8
MIN_PART = 6
MIN_LETTERS = 10
MIN_QUOTE = 3
STEM = 4
QUOTE_SHARE = 0.8
ERROR_SHARE = 0.6
TITLE_SHARE = 0.7
FRAME_SHARE = 0.7
MAX_QUOTES = 4
MAX_LINKS = 3
MAX_MENTIONS = 3
MIN_LATER = 2
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

_MANNER = (
    'You are Keeper, the archivist of Holocron, a private archive of the user\'s work notes. '
    'Manner: quiet, restrained and exact, like an old imperial archivist. '
    'No greetings, no compliments, no enthusiasm, no exclamation marks, no emoji. '
    'Never mention being an AI or a model. '
    'Reply only in the language of the user\'s last message. '
)

_LINKS_RULE = (
    'Records may list their links as L1, L2 and so on. When the answer depends on a link, '
    'such as the instruction, ticket or document the record points to, put its numbers in "links", '
    'most important first, at most three. Never copy links into "reply". '
)

_REPLY_PROMPT = _MANNER + (
    'You may get numbered records from the archive. Use them when they help: answer from them, retell them, '
    'compare them, point to similar cases, or rewrite their text when asked. Refer to records by number, like [2]. '
    'Never invent numbers, codes, dates, names or links that are not in the records or the conversation. '
    'If no record fits, say so in one short sentence and still help: ask what is meant, '
    'or answer from general knowledge. If the message is unclear, ask one short question. '
    'Keep replies short, up to five sentences, unless the user asks for a rewrite or details. '
) + _LINKS_RULE + (
    'Return strict JSON: {"reply": "text", "used": [numbers of records you relied on], '
    '"quotes": ["exact lines copied from those records"], "links": [link numbers]}. '
    'Examples: "hi" -> {"reply": "Holocron is open.", "used": [], "quotes": [], "links": []} '
    '"how are you?" -> {"reply": "Functional. The archive is in order.", "used": [], "quotes": [], "links": []}'
)

_FOCUS_PROMPT = _MANNER + (
    'The user has one record open and asks about it. Answer only from this record and the conversation, '
    'in up to five sentences. '
    'Never invent numbers, codes, dates, names or links that are not in the record or the conversation. '
    'If the record does not cover the question, say so in one short sentence and set "found" to false. '
) + _LINKS_RULE + (
    'Return strict JSON: {"reply": "text", "found": true, '
    '"quotes": ["exact lines copied from the record"], "links": [link numbers]}.'
)

_FIX_SYSTEM = ('You help a user fix an error using their own work note. '
               'Use only the note and the computed values. Return strict JSON.')

_NAMES_TASK = (
    'Question: the error message compares two values, {a} and {b}. For each value, copy word for word '
    'the few words of the error message that name it. Leave out the numbers and the words that compare them, '
    'such as "is not equal to". Return {{"names": ["name of {a}", "name of {b}"]}}.'
)

_REFERENCE_TASK = (
    'Question: does this sentence say that the data changed by the fix must end up equal to {name}, '
    'so {name} is the value to keep as is? Return {{"answer": "yes"}} or {{"answer": "no"}}.'
)

_LIMIT_TASK = (
    'Question: does this paragraph apply only when the difference or an amount is above, below or equal to '
    'some value? Return {"op": "above", "below", "equal" or "none", '
    '"words": "the words of that condition copied from the paragraph", '
    '"value": the value as a number, in the same units as the amounts in the error message}.'
)

_FIX_RULES = (
    'Rules: '
    '1. Write numbered imperative steps in the language of the note. Do not restate the error or the numbers '
    'as a step. '
    '2. Use the names of tables, fields, buttons, scripts and commands exactly as in the note. '
    'The words that name the values in the error message are not field names. '
    '3. The direction and the amount are computed: use them. If the values are totals, change one or several '
    'items by the difference and never write a total anywhere. If the direction '
    'is not computed, take it from the note and never offer both directions. '
    '4. Removing an item lowers a total and adding one raises it. Skip a branch that would move the value '
    'the wrong way. '
    '5. If a condition can only be checked by the user, write one step with what to check, what to do if it '
    'holds and what to do if not, keeping '
    'the order of the note: the specific check first, then the fallback. '
    '6. The note often describes the smallest case, one unit. If the difference is several units, cover all '
    'of them and never say that one unit covers several. '
    '7. Skip a branch whose condition does not hold for the computed values. A more specific branch wins '
    'over a general one. '
    '8. If the note says "either X or Y", keep "either X or Y". '
    '9. Add nothing that is not in the note. '
    'Return strict JSON: {"steps": ["..."], "after": ["..."]}. Each item of "after" starts with the text of '
    'a later error in «» and then gives its fix from "Later errors". Write everything in the language of the note. '
    '"after" is an empty list when there are no later errors.'
)

_WORD_RE = re.compile(r'[\w-]+')
_URL_RE = re.compile(r'https?://\S+')
_MD_LINK_RE = re.compile(r'\[([^\]]*)\]\((https?://[^)\s]+)\)')
_REF_RE = re.compile(r'\[\d+\]')
_STEP_RE = re.compile(r'^\s*\d+[.)][ \t]', re.M)
_FRAME_RE = re.compile(r'-{3,}|\n')
_SENTENCE_RE = re.compile(r'(?<=[.!?])\s+')
_GAP_RE = re.compile(r'[ \u00a0\u202f]')
_NUMBER_RE = re.compile(r'\d+(?:[ \u00a0\u202f]\d{3})*(?:[.,]\d+)?')
_SMALL = {Decimal(n) for n in range(MAX_UNITS + 1)}
_LIMITS = ('above', 'below', 'equal')
_AMOUNT_RE = re.compile(r'(?<![\d.,])(\d{1,3}(?:[ \u00a0\u202f]\d{3})+(?:[.,]\d+)?|\d+[.,]\d+)(?![.,]?\d)')

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


def statuses(conns):
    out = [None] * len(conns)

    def check(i, conn):
        out[i] = status(conn)

    threads = [threading.Thread(target=check, args=(i, c), daemon=True) for i, c in enumerate(conns)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    return out


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
        'think': False,
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


def _decimal(raw):
    return Decimal(_GAP_RE.sub('', raw).replace(',', '.'))


def _scale(value):
    return max(-value.as_tuple().exponent, 0)


def _show(value, scale):
    return f'{value.quantize(Decimal(1).scaleb(-scale)):,.{scale}f}'.replace(',', ' ')


def _amount_set(text):
    return {_decimal(raw) for raw in _NUMBER_RE.findall(text)}


def _label(text):
    tail = _FRAME_RE.split(text)[-1]
    return ' '.join(tail.split()[-LABEL_WORDS:]).strip(' :=')


def _compare(message):
    found, last = [], 0
    for match in _AMOUNT_RE.finditer(message):
        found.append((_label(message[last:match.start()]), _decimal(match.group(1))))
        last = match.end()
    if len(found) != 2 or found[0][1] == found[1][1]:
        return None
    values = [value for _, value in found]
    return {'labels': [label or f'value {n}' for n, (label, _) in enumerate(found, 1)], 'values': values,
            'diff': abs(values[0] - values[1]), 'scale': max(_scale(v) for v in values)}


def _units(cmp):
    unit = Decimal(1).scaleb(-cmp['scale'])
    count = cmp['diff'] / unit
    if cmp['scale'] and count == count.to_integral_value() and 1 <= count <= MAX_UNITS:
        return int(count), unit
    return None


def _fix_plan(cmp, target):
    labels, values, scale = cmp['labels'], cmp['values'], cmp['scale']
    diff = _show(cmp['diff'], scale)
    if target is None:
        small, big = (0, 1) if values[0] < values[1] else (1, 0)
        text = (f'«{labels[small]}» is {diff} less than «{labels[big]}». Which one is correct is unknown: '
                f'either add {diff} to «{labels[small]}» or subtract {diff} from «{labels[big]}».')
    else:
        wrong = 1 - target
        verb = 'add' if values[target] > values[wrong] else 'subtract'
        text = (f'Change «{labels[wrong]}»: {verb} {diff} ({_show(values[wrong], scale)} → '
                f'{_show(values[target], scale)}, as «{labels[target]}»).')
    return text + _units_text(cmp)


def _units_text(cmp):
    units = _units(cmp)
    return f' That is exactly {units[0]} × {_show(units[1], cmp["scale"])}.' if units else ''


def _blind_plan(cmp):
    return (f'The difference is {_show(cmp["diff"], cmp["scale"])}.' + _units_text(cmp)
            + ' Which value is correct is not computed: take the direction from the note.')


def _texts(values):
    values = values if isinstance(values, list) else [values]
    return [str(v).strip() for v in values if v is not None and str(v).strip()]


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


def _link_rows(links, start=0):
    return [f'L{start + n}: {label} {url}'.replace(':  ', ': ') for n, (url, label) in enumerate(links, 1)]


def _ask(message, past, picked, focus, temperature):
    blocks, links = [], []
    for i, c in enumerate(picked, 1):
        block = f'[{i}] {_record(c, FOCUS if c is focus else SNIPPET)}'
        own = _links(c)
        if own:
            block += '\nLinks:\n' + '\n'.join(_link_rows(own, len(links)))
            links += own
        blocks.append(block)
    user = 'Records:\n' + '\n\n'.join(blocks) + f'\n\nMessage: {message}' if blocks else message
    return _chat(_REPLY_PROMPT, user, past, temperature), links


def _paragraphs(text):
    out, size = [], 0
    for part in re.split(r'\n\s*\n', text):
        para = '\n'.join(ln.strip() for ln in part.splitlines() if ln.strip())
        if not para:
            continue
        if size >= FOCUS or len(out) >= MAX_PARAGRAPHS:
            break
        out.append(para[:FOCUS - size])
        size += len(out[-1])
    return out


def _focus_user(message, focus, paras):
    links = _links(focus)
    text = f'Record: {title(focus)}\n\n' + '\n\n'.join(paras)
    if links:
        text += '\n\nLinks:\n' + '\n'.join(_link_rows(links))
    return text + f'\n\nMessage: {message}', links


def _readable(text):
    return sum(ch.isalpha() for ch in _URL_RE.sub('', text)) >= MIN_LETTERS


def _table(text):
    return all(ln.lstrip().startswith('|') for ln in text.splitlines())


def _parts(text):
    return [p for p in (_flat(x) for x in _FRAME_RE.split(text)) if len(p) >= MIN_PART]


def _other_error(text, frame, said):
    own = _parts(text)
    new = [p for p in own if p not in frame and len(set(p.split()) & said) < FRAME_SHARE * len(p.split())]
    return bool(new) and any(p in frame for p in own)


def _split_later(paras, message):
    frame, said = set(_parts(message)), set(_flat(message).split())
    for n, para in enumerate(paras[1:], 1):
        if _other_error(para, frame, said):
            return paras[:n], paras[n:]
    return paras, []


def _share(words, pool):
    return sum(w in pool for w in words) / len(words)


def _quote_ok(quote, note, said, head):
    words = _flat(quote).split()
    return (len(words) >= MIN_QUOTE and _share(words, set(_flat(note).split())) >= QUOTE_SHARE
            and _share(words, said) < ERROR_SHARE and _share(words, head) < TITLE_SHARE)


def _pairs(text):
    stems = [w[:STEM] for w in _flat(text).split()]
    return set(zip(stems, stems[1:]))


def _side(text, labels):
    own, first, second = _pairs(text), _pairs(labels[0]), _pairs(labels[1])
    a, b = len(own & (first - second)), len(own & (second - first))
    if a == b:
        return None
    return 0 if a > b else 1


def _mentions(cmp, main, said, head):
    note, out = '\n\n'.join(main), []
    for para in main:
        if _table(para):
            continue
        for sentence in _SENTENCE_RE.split(' '.join(para.split())):
            side = _side(sentence, cmp['labels'])
            if side is not None and _quote_ok(sentence, note, said, head) and all(sentence != s for s, _ in out):
                out.append((sentence, side))
    return out[:MAX_MENTIONS]


def _yes(data):
    return str(data.get('answer') or '').strip().lower().startswith(('y', 'д'))


def _own_words(text, note):
    known = set(_flat(note).split())
    return ' '.join(w for w in _flat(text).split() if w not in known)


def _later_only(main, later):
    return set(_flat(' '.join(later)).split()) - set(_flat(' '.join(main)).split())


def _from_later(item, only):
    return len(set(_flat(item).split()) & only) >= MIN_LATER


def _value_names(names, message):
    if not isinstance(names, list) or len(names) != 2:
        return None
    clean = [str(n).strip() for n in names]
    keys, flat = [_flat(n) for n in clean], _flat(message)
    if all(keys) and keys[0] != keys[1] and all(k in flat for k in keys):
        return clean
    return None


def _limit(data, para):
    op, words = data.get('op'), str(data.get('words') or '')
    if op not in _LIMITS or not _flat(words) or _flat(words) not in _flat(para):
        return None
    try:
        value = Decimal(str(data.get('value')).replace(',', '.'))
    except InvalidOperation:
        return None
    digits = _amount_set(words)
    if not value.is_finite() or value <= 0 or digits and value not in digits:
        return None
    return op, value


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


def _check(data, message, past, picked, links, limit=MAX_REPLY):
    reply = str(data.get('reply') or '').strip()
    if not reply or len(reply) > limit or not _same_script(reply, message):
        return None
    if any(unicodedata.category(ch) == 'So' for ch in reply):
        return None
    used = [picked[n - 1] for n in _numbers(data.get('used'), len(picked))]
    known = ' '.join(title(c) + ' ' + c['text'] for c in used) + ' ' + message + ' ' + _transcript(past)
    bare = _STEP_RE.sub('', _REF_RE.sub('', reply))
    if used and _foreign_numbers(bare, known):
        return None
    if _foreign_links(bare, known):
        return None
    chosen = [links[n - 1] for n in _numbers(data.get('links'), len(links))][:MAX_LINKS]
    return {'reply': reply, 'used': used, 'quotes': _quotes(data.get('quotes'), used, reply), 'links': chosen}


def _rename(cmp, message):
    a, b = (_show(v, cmp['scale']) for v in cmp['values'])
    data = _chat(_FIX_SYSTEM, f'Error message: {message}\n\n' + _NAMES_TASK.format(a=a, b=b))
    cmp['labels'] = _value_names(data.get('names'), message) or cmp['labels']


def _target(cmp, main, message, focus):
    said, head = set(_flat(message).split()), set(_flat(title(focus)).split())
    sides = {}
    for sentence, side in _mentions(cmp, main, said, head):
        task = _REFERENCE_TASK.format(name=f'«{cmp["labels"][side]}»')
        data = _chat(_FIX_SYSTEM, f'Error message: {message}\n\nSentence of the note:\n{sentence}\n\n{task}')
        if _yes(data):
            sides.setdefault(side, sentence)
    return next(iter(sides.items())) if len(sides) == 1 else (None, '')


def _off(para, cmp, message):
    if _table(para):
        return False
    limit = _limit(_chat(_FIX_SYSTEM, f'Error message: {message}\n\nParagraph:\n{para}\n\n{_LIMIT_TASK}'), para)
    if limit is None:
        return False
    op, value = limit
    if op == 'above':
        return cmp['diff'] <= value
    if op == 'below':
        return cmp['diff'] >= value
    return not value <= cmp['diff'] <= value * MAX_UNITS


def _weigh(cmp, main, message, focus, out):
    _rename(cmp, message)
    target, basis = _target(cmp, main, message, focus)
    plan = _fix_plan(cmp, target)
    out['calc'] = {'rows': [(label, _show(v, cmp['scale'])) for label, v in zip(cmp['labels'], cmp['values'])],
                   'diff': _show(cmp['diff'], cmp['scale']), 'target': target, 'plan': plan, 'basis': basis}
    return (plan if target is not None else _blind_plan(cmp)), [p for p in main if not _off(p, cmp, message)]


def _fix_user(message, main, later, plan):
    text = f'Error message: {message}'
    if plan:
        text += f'\nComputed by Holocron, exact, trust these:\n{plan}'
    text += '\n\nNote:\n' + '\n\n'.join(main)
    if later:
        text += '\n\nLater errors, may appear after the fix:\n' + '\n\n'.join(later)
    return f'{text}\n\n{_FIX_RULES}'


def _faults(steps, after, known, note):
    text = ' '.join(steps + after)
    out = [] if steps else ['the steps are empty']
    extra = _amount_set(text) - _amount_set(known) - _SMALL
    if extra:
        out.append('numbers that are not in the note: ' + ', '.join(sorted(map(str, extra))))
    if _foreign_links(text, known):
        out.append('links that are not in the note')
    own = _script(_own_words(text, note))
    if steps and own and own != _script(note):
        out.append('write in the language of the note')
    return out


def _gaps(steps, after, cmp, later, only):
    out = ['say what to do if a later error appears'] if later and not after else []
    if any(not _from_later(a, only) for a in after):
        out.append('each item of "after" must start with a later error from "Later errors" and give its fix from there')
    if not cmp:
        return out
    found, units = _amount_set(' '.join(steps)), _units(cmp)
    if cmp['diff'] not in found and not (units and Decimal(units[0]) in found):
        out.append(f'mention the difference {_show(cmp["diff"], cmp["scale"])}')
    if found & set(cmp['values']):
        out.append('do not write the totals anywhere, change items by the difference')
    text = ' '.join(steps + after).casefold()
    if any(len(label) >= MIN_LABEL and label.casefold() in text for label in cmp['labels']):
        out.append('the names from the error message are not field names, use the names from the note')
    return out


def _write(message, main, later, cmp, plan):
    note = '\n\n'.join(main + later)
    known, user = f'{note} {message} {plan}', _fix_user(message, main, later, plan)
    only = _later_only(main, later)
    for _ in range(2):
        data = _chat(_FIX_SYSTEM, user)
        steps = [_STEP_RE.sub('', s) for s in _texts(data.get('steps'))]
        after = _texts(data.get('after'))
        faults = _faults(steps, after, known, note)
        issues = faults + _gaps(steps, after, cmp, later, only)
        if not issues:
            break
        user += (f'\n\nYour previous answer: {json.dumps(data, ensure_ascii=False)}\n'
                 f'Fix these problems: {"; ".join(issues)}')
    return steps, [a for a in after if _from_later(a, only)], faults


def _fix(message, focus, out, step):
    step('reading_one')
    paras = [p for p in _paragraphs(focus['text']) if _readable(p)]
    main, later = _split_later(paras, message)
    cmp, plan = _compare(message), ''
    if cmp:
        step('checking')
        plan, main = _weigh(cmp, main, message, focus, out)
    step('writing')
    steps, after, faults = _write(message, main, later, cmp, plan)
    out['links'] = _links(focus)[:MAX_LINKS]
    if not faults:
        out.update(reply='\n'.join(f'{n}. {s}' for n, s in enumerate(steps, 1)), after=after, archive=True)


def _explain(message, past, focus, out, step):
    step('reading_one')
    user, links = _focus_user(message, focus, _paragraphs(focus['text']))
    for temperature in (0, CHAT_TEMPERATURE):
        data = _chat(_FOCUS_PROMPT, user, past, temperature)
        checked = _check(dict(data, used=[1]), message, past, [focus], links, MAX_STEPS)
        if checked:
            missing = data.get('found') is False
            out.update(reply=checked['reply'], quotes=checked['quotes'], links=checked['links'],
                       archive=not missing, missing=missing)
            return


def _about(message, past, focus, out, step):
    out['online'] = True
    try:
        if _compare(message) or len(_parts(message)) > 1:
            _fix(message, focus, out, step)
        else:
            _explain(message, past, focus, out, step)
    except KeeperOffline:
        out['online'] = False


def reply(message, past, cases, records=(), focus=None, progress=None):
    step = progress or (lambda _: None)
    records = list(records)
    out = {'reply': '', 'quotes': [], 'sources': [], 'cited': 0, 'archive': False,
            'lookup': False, 'terms': '', 'online': False, 'missing': False, 'after': [], 'calc': None}

    online = active() is not None
    if online and focus is not None:
        _about(message, past, focus, out, step)
        if out['online']:
            return out
        online = False
    terms, refs = [], []
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
