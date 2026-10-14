BROKEN = (OSError, ValueError, KeyError, TypeError, AttributeError)


def _stamp(path):
    st = path.stat()
    return st.st_mtime_ns, st.st_size


class Archive:
    name = ''
    key = ''

    def __init__(self):
        self._cases = []
        self._path = None
        self._files = {}
        self._loaded = False

    def is_configured(self):
        return False

    def load(self, force=False):
        if force:
            self._files = {}
        self._load()
        self._loaded = True

    def _load(self):
        pass

    def _reset(self):
        self._cases, self._path, self._files = [], None, {}

    def _read(self, files, parse):
        old, self._files, cases = self._files, {}, []
        for f in files:
            try:
                stamp = _stamp(f)
            except OSError:
                continue
            hit = old.get(str(f))
            found = hit[1] if hit and hit[0] == stamp else parse(f)
            self._files[str(f)] = (stamp, found)
            cases.extend(found)
        return cases

    def load_cases(self):
        if not self._loaded:
            self.load()
        return self._cases

    def path(self):
        return self._path

    def tagged_cases(self):
        cases = self.load_cases()
        for c in cases:
            c['archive'] = self.name
        return cases
