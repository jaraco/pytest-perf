from __future__ import annotations

import functools
from collections.abc import Callable
from typing import Any, TypeVar

_F = TypeVar('_F', bound=Callable[..., Any])


def decorate(name: str, *items: Any) -> Callable[[_F], _F]:
    """
    Build a decorator to extend a list of items on a function.
    """

    def apply(func: _F) -> _F:
        values = vars(func).setdefault(name, [])
        values.extend(items)
        return func

    return apply


extras = functools.partial(decorate, 'extras')
deps = functools.partial(decorate, 'deps')


def control(rev: str) -> Callable[[_F], _F]:
    def apply(func: _F) -> _F:
        func.control = rev  # type: ignore[attr-defined]
        return func

    return apply
