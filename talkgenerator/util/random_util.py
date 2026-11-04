import random
from collections.abc import Sequence
from typing import TypeVar

T = TypeVar("T")


# From https://stackoverflow.com/questions/14992521/python-weighted-random
def weighted_random(pairs: Sequence[tuple[float, T]]) -> T | None:
    if len(pairs) == 0:
        return None
    total = sum(pair[0] for pair in pairs)
    r = random.uniform(0, total)
    for weight, value in pairs:
        r -= weight
        if r <= 0:
            return value
    return None


def choice_optional(lst: Sequence[T]) -> T | None:
    """ " Returns random.choice if there are elements, None otherwise"""
    if len(lst) > 0:
        return random.choice(lst)
    return None
