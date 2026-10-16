import math
import os
import re
import difflib
from functools import lru_cache


MATCH_MIN = 0.6
MIN_COVERAGE = 0.5
EXACT = 0.9
EXACT_BONUS = 10.0
FORM = 0.9
TYPO = 0.85
PREFIX_MIN = 4
ABBR_MIN = 5
FORM_TAIL = 3
PHRASE_MIN = 4
_WORD_RE = re.compile(r"\w+")
_PUNCT = ".,;:!?()[]{}\"'«»—–…"
_ALNUM_RE = re.compile(r'([^\W\d_]+)(\d+)', re.UNICODE)


def _normalize_search_text(text):
    text = text.lower().replace('ё', 'е').replace('_', ' ')
    text = re.sub(r'-{2,}', ' ', text)
    text = re.sub(r'(?<=\w)-(?=\w)', ' ', text)
    return text


def _doc_prefixes(text):
    prefixes = set()
    for m in _ALNUM_RE.finditer(text):
        if len(m.group(1)) >= 2:
            prefixes.add(m.group(1))
    for token in _WORD_RE.findall(text):
        m = re.fullmatch(r'([а-яёa-z]+)(\d+)', token)
        if m and len(m.group(1)) >= 2:
            prefixes.add(m.group(1))
            prefixes.add(m.group(2))
    return prefixes


def _prep(case):
    filename = case.get("filename", "")
    key = (filename, case["text"])
    if case.get("_prep_for") != key:
        searchable = filename + "\n" + case["text"] if filename else case["text"]
        low = _normalize_search_text(searchable)
        case["_low"] = low
        case["_flat"] = re.sub(r"\s+", " ", low)
        tokens = set(_WORD_RE.findall(low))
        tokens |= _doc_prefixes(low)
        case["_tokens"] = tokens
        case["_title"] = _normalize_search_text("\n".join(searchable.splitlines()[:2]))
        case["_title_tokens"] = set(_WORD_RE.findall(case["_title"])) | _doc_prefixes(case["_title"])
        case["_prep_for"] = key
    return case


def _norm_words(query):
    out = []
    for w in re.split(r"\s+", _normalize_search_text(query)):
        if not w:
            continue
        stripped = w.strip(_PUNCT + '-')
        token = stripped or w
        if not token or not any(c.isalnum() for c in token):
            continue
        out.append(token)
        m = re.fullmatch(r'([а-яёa-z]+)(\d+)', token)
        if m and len(m.group(1)) >= 2:
            out.append(m.group(1))
    return out


@lru_cache(maxsize=256)
def _query(query):
    flat = re.sub(r"\s+", " ", _normalize_search_text(query)).strip()
    return tuple(_norm_words(query)), flat


@lru_cache(maxsize=65536)
def similarity(qw, tw):
    r = difflib.SequenceMatcher(None, qw, tw).ratio()
    if tw.startswith(qw) or qw.startswith(tw):
        r = max(r, 0.85)
    return r


def _edits(a, b, limit):
    if abs(len(a) - len(b)) > limit:
        return limit + 1
    before, prev = None, list(range(len(b) + 1))
    for i, ca in enumerate(a, 1):
        cur = [i] + [0] * len(b)
        for j, cb in enumerate(b, 1):
            cur[j] = min(prev[j] + 1, cur[j - 1] + 1, prev[j - 1] + (ca != cb))
            if i > 1 and j > 1 and ca == b[j - 2] and a[i - 2] == cb:
                cur[j] = min(cur[j], before[j - 2] + 1)
        if min(cur) > limit:
            return limit + 1
        before, prev = prev, cur
    return prev[-1]


def _exact_only(word):
    if len(word) <= 3:
        return True
    if any(ch.isdigit() for ch in word):
        return True
    return False


@lru_cache(maxsize=65536)
def word_match(qw, tw):
    if qw == tw:
        return 1.0
    if _exact_only(qw) or _exact_only(tw) or qw[0] != tw[0]:
        return 0.0
    short, long_ = sorted((len(qw), len(tw)))
    if len(qw) >= ABBR_MIN and tw.startswith(qw):
        return FORM
    prefix = len(os.path.commonprefix((qw, tw)))
    if prefix >= max(PREFIX_MIN, short - FORM_TAIL) and long_ - short <= max(FORM_TAIL, short // 2):
        return FORM
    limit = 1 if long_ <= 7 else 2
    return TYPO if _edits(qw, tw, limit) <= limit else 0.0


def _matches(qw, vocab):
    if not _WORD_RE.fullmatch(qw):
        return None
    if _exact_only(qw):
        return {qw: 1.0} if qw in vocab else {}
    head = qw[0]
    return {tw: s for tw in vocab if tw[0] == head and (s := word_match(qw, tw))}


def _hit(case, qw, found):
    if found is None:
        return 1.0 if qw in case["_low"] else 0.0
    return max((found[t] for t in case["_tokens"] & found.keys()), default=0.0)


def _context(cases, words):
    vocab = set()
    for c in cases:
        _prep(c)
        vocab |= c["_tokens"]
    table = [_matches(qw, vocab) for qw in words]
    hits = [[_hit(c, qw, m) for qw, m in zip(words, table)] for c in cases]
    n = len(cases)
    dfs = [sum(1 for h in hits if h[i]) for i in range(len(words))]
    known = [math.log(1 + n / df) for df in dfs if df]
    floor = min(known) if known else math.log(1 + n)
    weights = [math.log(1 + n / df) if df else floor for df in dfs]
    return hits, weights


def _longest_phrase_run(words, flat, cap=8):
    best = 1
    limit = min(len(words), cap)
    for size in range(2, limit + 1):
        needle_found = False
        for i in range(len(words) - size + 1):
            if " ".join(words[i:i + size]) in flat:
                needle_found = True
                break
        if not needle_found:
            break
        best = size
    return best


def _score(case, hit, weights, words, q_flat):
    matched = [h for h in hit if h]
    if len(words) <= 2:
        if len(matched) < len(words):
            return 0
    elif len(matched) < 2:
        return 0
    total = sum(weights)
    got = sum(w for w, h in zip(weights, hit) if h)
    coverage = got / total if total else 0
    run = _longest_phrase_run(words, case["_flat"]) if len(words) > 2 else 1
    if len(words) > 2 and coverage < MIN_COVERAGE and run < PHRASE_MIN:
        return 0

    quality = sum(matched) / len(matched)
    base = quality * coverage
    for qw, h in zip(words, hit):
        if h == 1.0 and _ALNUM_RE.fullmatch(qw):
            base += 0.5
            break

    title_low, title_tokens = case["_title"], case["_title_tokens"]
    title_hits = sum(
        1 for qw in words
        if (qw in title_tokens if len(qw) <= 3 else qw in title_low)
    )
    if title_hits:
        base += 0.4 * (title_hits / len(words))

    title_flat = re.sub(r"\s+", " ", title_low)
    if q_flat and q_flat in case["_flat"]:
        base += 0.5
        if q_flat in title_flat:
            base += 1.0
        filename = case.get("filename", "")
        if filename and _normalize_search_text(filename).strip() == q_flat:
            base += 1.0
    elif len(words) > 2:
        if run > 1:
            base += 0.6 * (run / len(words))

    score = base - min(len(case["text"]) / 2000.0, 0.5)
    if score > 0 and coverage >= EXACT:
        score += EXACT_BONUS
    return score


def score_case(case, query):
    words, q_flat = _query(query)
    if not words:
        return 0
    hits, weights = _context([case], words)
    return _score(case, hits[0], weights, words, q_flat)


def search(cases, query):
    words, q_flat = _query(query)
    if not words or not cases:
        return []
    hits, weights = _context(cases, words)
    s = [(_score(c, h, weights, words, q_flat), c) for c, h in zip(cases, hits)]
    s = [t for t in s if t[0] > 0]
    s.sort(key=lambda t: -t[0])
    return s


def is_exact(score):
    return score >= EXACT_BONUS


def suggest(cases, q):
    words = _norm_words(q)
    if not words:
        return []

    vocab = {w for c in cases for w in re.findall(r"\w{3,}", c["text"].lower())}

    fixed = []
    changed = False
    any_known = False
    for w in words:
        matches = difflib.get_close_matches(w, vocab, n=1, cutoff=0.7)
        if matches:
            any_known = True
            if matches[0] != w:
                fixed.append(matches[0])
                changed = True
            else:
                fixed.append(w)
        else:
            fixed.append(w)

    if not changed or not any_known:
        return []

    candidate = " ".join(fixed)
    if search(cases, candidate):
        return [candidate]
    return []
