from pytest_perf.deco import extras, deps, control


@extras('testing')
@deps('path')
def deps_and_extras_perf():
    "with deps and extras"
    import path
    import pytest  # end warmup

    assert type(pytest) is type(path)


def simple_perf_test():
    "simple test"
    import abc
    import types  # end warmup

    dir(abc)
    assert isinstance(abc, types.ModuleType)


@control('v0.9.2')
def diff_from_oh_nine_two_perf():
    pass


def check_perf_isolated():
    import pytest_perf  # end warmup

    path = str(pytest_perf.__path__)
    assert 'pip-run' in path, path
