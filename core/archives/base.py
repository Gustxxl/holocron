class Archive:
    name = ''
    key = ''

    def is_configured(self):
        return False

    def load(self):
        pass

    def load_cases(self):
        return []

    def tagged_cases(self):
        cases = self.load_cases()
        for c in cases:
            c['archive'] = self.name
        return cases
