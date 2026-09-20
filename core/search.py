import re
import difflib


MATCH_MIN = 0.6
MIN_COVERAGE = 0.5
_WORD_RE = re.compile(r"\w+")
_PUNCT = ".,;:!?()[]{}\"'«»—–…"


def _normalize_search_text(text):
    text = text.lower()
    text = re.sub(r"(?<=\d)(?=[а-яё])|(?<=[а-яё])(?=\d)", " ", text)
    return text


def _prep(case):
    if case.get("_prep_for") != case["text"]:
        low = _normalize_search_text(case["text"])
        case["_low"] = low
        case["_flat"] = re.sub(r"\s+", " ", low)
        case["_tokens"] = set(_WORD_RE.findall(low))
        case["_title"] = "\n".join(case["text"].splitlines()[:2]).lower()
        case["_prep_for"] = case["text"]
    return case


def _norm_words(query):
    out = []
    for w in re.split(r"\s+", _normalize_search_text(query)):
        if not w:
            continue
        stripped = w.strip(_PUNCT)
        out.append(stripped or w)
    return out


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


def _word_score(qw, text_low, tokens):
    if qw in text_low:
        return 1.0
    if len(qw) <= 3:
        return 0.0
    best = 0.0
    for tw in tokens:
        if abs(len(tw) - len(qw)) > 3:
            continue
        r = difflib.SequenceMatcher(None, qw, tw).ratio()
        if tw.startswith(qw) or qw.startswith(tw):
            r = max(r, 0.85)
        if r > best:
            best = r
            if best >= 0.95:
                break
    return best


def score_case(case, query):
    _prep(case)
    text_low, title_low = case["_low"], case["_title"]
    words = _norm_words(query)
    if not words:
        return 0

    scores = [_word_score(qw, text_low, case["_tokens"]) for qw in words]
    matched = [s for s in scores if s >= MATCH_MIN]

    if len(words) <= 2:
        if len(matched) < len(words):
            return 0
    else:
        if len(matched) < 2 or len(matched) / len(words) < MIN_COVERAGE:
            return 0

    coverage = len(matched) / len(words)
    quality = sum(matched) / len(matched)
    base = quality * coverage

    title_hits = sum(1 for qw in words if qw in title_low)
    if title_hits:
        base += 0.4 * (title_hits / len(words))

    q_flat = re.sub(r"\s+", " ", _normalize_search_text(query)).strip()
    if q_flat and q_flat in case["_flat"]:
        base += 0.5
    elif len(words) > 2:
        run = _longest_phrase_run(words, case["_flat"])
        if run > 1:
            base += 0.6 * (run / len(words))

    return base - min(len(case["text"]) / 2000.0, 0.5)


def search(cases, query):
    s = [(score_case(c, query), c) for c in cases]
    s = [t for t in s if t[0] > 0]
    s.sort(key=lambda t: -t[0])
    return s


def suggest(cases, q):
    vocab = {w for c in cases for w in re.findall(r"\w{3,}", c["text"].lower())}
    return difflib.get_close_matches(q.lower(), vocab, n=5, cutoff=0.6)
