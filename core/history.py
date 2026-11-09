from core.settings import PAGE_MAX

_QUERIES = []


def add(query):
    key = query.casefold()
    _QUERIES[:] = [query, *(q for q in _QUERIES if q.casefold() != key)][:PAGE_MAX]


def recent(limit):
    return _QUERIES[:limit]
