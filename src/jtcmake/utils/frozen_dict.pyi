from collections.abc import Mapping

class FrozenDict(Mapping):
    def __init__(self, dic: Mapping):
        ...

    def __getitem__(self, key):
        ...

    def __iter__(self):
        ...

    def __len__(self) -> int:
        ...

    def __contains__(self, key) -> bool:
        ...

    def __repr__(self) -> str:
        ...

    def __getattr__(self, key):
        ...

