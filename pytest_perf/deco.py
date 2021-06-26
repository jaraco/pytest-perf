import functools


def decorate(name, *items):
    """
    Build a decorator to extend a list of items on a function.
    """

    def apply(func):
        values = vars(func).setdefault(name, [])
        values.extend(items)
        return func

    return apply


extras = functools.partial(decorate, 'extras')
deps = functools.partial(decorate, 'deps')
