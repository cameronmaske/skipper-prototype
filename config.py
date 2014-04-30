import json


class BaseConfig(dict):
    def __init__(self, *args, **kwargs):
        self._store = self.retrieve()

    def __repr__(self):
        return self._store.__repr__()

    def __setitem__(self, key, value):
        self._store[key] = value
        self.save()

    def __getitem__(self, key):
        return self._store[key]

    def __delitem__(self, key):
        del self._store[key]
        self.save()

    def retrieve(self):
        return {}

    def save(self):
        pass


class Config(BaseConfig):
    def retrieve(self):
        with open('config.json', 'r+') as f:
            try:
                return json.load(f)
            except ValueError:
                return {}

    def save(self):
        with open('config.json', 'w+') as f:
            f.write(json.dumps(self._store, indent=2))


