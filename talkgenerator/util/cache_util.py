# from https://stackoverflow.com/questions/1151658/python-hashable-dicts
class HashableDict(dict):
    """A hashable version of a dictionary, useful for when a function needs to be cached but uses a dict as an
    argument"""

    def __key(self):
        return tuple((k, self[k]) for k in sorted(self))

    def __hash__(self):
        return hash(self.__key())

    def __eq__(self, other):
        return self.__key() == other.__key()
