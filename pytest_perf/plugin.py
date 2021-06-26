import pytest
import functools
import importlib
import re
import inspect
import textwrap
import contextlib

from typing import List
from jaraco.functools import assign_params, pass_none, apply
from more_itertools import peekable

from pytest_perf import runner


def pytest_collect_file(parent, path):
    if path.basename.endswith('.py'):
        return File.from_parent(parent, fspath=path)


def pytest_terminal_summary(terminalreporter, config):
    items = peekable(filter(None, Experiment._instances))
    items and terminalreporter.section('perf')
    for line in map(str, items):
        terminalreporter.write_line(line)


def pytest_sessionfinish():
    """
    Clear the runner factory to tear down any BenchmarkRunners.
    """
    runner_factory.cache_clear()


class File(pytest.File):
    def collect(self):
        return (
            Experiment.from_parent(self, name=f'{self.name}:{spec["name"]}', spec=spec)
            for spec in map(spec_from_func, funcs_from_name(self.name))
        )


runner_factory = functools.lru_cache()(runner.BenchmarkRunner)


def funcs_from_name(name):
    mod_path, sep, rest = name.rpartition('.')
    mod_name = mod_path.replace('/', '.')
    mod = importlib.import_module(mod_name)
    return (
        getattr(mod, name) for name in dir(mod) if re.search(r'(\b|_)perf(\b|_)', name)
    )


def first_line(text):
    lines = (line.strip() for line in text.splitlines())
    return next(lines, None)


freeze = pass_none(tuple)


@apply(dict)
def spec_from_func(_func):
    yield 'name', (first_line(_func.__doc__) or _func.__name__)
    with contextlib.suppress(AttributeError):
        yield 'extras', freeze(_func.extras)
    with contextlib.suppress(AttributeError):
        yield 'deps', freeze(_func.deps)
    _header, _sep, _body_ind = inspect.getsource(_func).partition(':\n')
    _body = textwrap.dedent(_body_ind)
    warmup, sep, exercise = _body.rpartition('# end warmup')
    if warmup:
        yield 'warmup', warmup
    yield 'exercise', exercise


class Experiment(pytest.Item):
    _instances: 'List[Experiment]' = []

    def __init__(self, name, parent, spec):
        super().__init__(name, parent)
        self.spec = spec
        self.command = assign_params(runner.Command, spec)()
        Experiment._instances.append(self)

    def runtest(self):
        self.results = self.runner.run(self.command)

    @property
    def runner(self):
        return assign_params(runner_factory, self.spec)()

    def reportinfo(self):
        return self.fspath, 0, self.name

    def __str__(self):
        return f'{self.name}: {self.results}'

    def __bool__(self):
        return hasattr(self, 'results')
