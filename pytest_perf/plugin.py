import functools
import importlib
import re
import inspect
import textwrap
import contextlib

import pytest
from typing import List
from packaging.version import Version
from jaraco.functools import assign_params, pass_none, apply
from jaraco.context import suppress
from more_itertools import peekable

from pytest_perf import runner


def pytest_addoption(parser):
    group = parser.getgroup("performance tests (pytest-perf)")
    group.addoption(
        "--perf-target",
        help="directory or distribution file for which the performance tests will run",
    )
    group.addoption(
        "--perf-baseline",
        help="URL to a git repository to be used as a performance comparison; "
        "defaults to `origin` remote of local repo",
    )


def _collect_file_pytest7(parent, file_path):
    if file_path.suffix == '.py' and 'pytest_perf' in file_path.read_text(
        encoding='utf-8'
    ):
        return File.from_parent(parent, path=file_path)


def _collect_file_pytest6(parent, path):
    if path.basename.endswith('.py') and 'pytest_perf' in path.read_text(
        encoding='utf-8'
    ):
        return File.from_parent(parent, fspath=path)


old_pytest = Version(pytest.__version__) < Version('7')
pytest_collect_file = suppress(UnicodeDecodeError)(
    _collect_file_pytest6 if old_pytest else _collect_file_pytest7)


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
            for spec in map(spec_from_func, funcs_from_name(self.path))
        )


runner_factory = functools.lru_cache()(runner.BenchmarkRunner)


@suppress(Exception)
def load_module(path):
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def funcs_from_name(path):
    mod = load_module(path)
    return (
        getattr(mod, name) for name in dir(mod) if re.search(r'(\b|_)perf(\b|_)', name)
    )


@pass_none
def first_line(text):
    lines = (line.strip() for line in text.splitlines())
    return next(lines, None)


freeze = pass_none(tuple)


@apply(dict)
def spec_from_func(_func):
    r"""
    Given a function from an experiment file, return a
    spec (dictionary) representing that experiment.

    >>> import exercises
    >>> spec = spec_from_func(exercises.simple_perf_test)
    >>> list(spec)
    ['name', 'warmup', 'exercise']
    >>> spec['name']
    'simple test'
    >>> spec['warmup']
    '"simple test"\nimport abc\nimport types  '
    >>> spec['exercise']
    '\n\ndir(abc)\nassert isinstance(abc, types.ModuleType)\n'

    >>> spec = spec_from_func(exercises.deps_and_extras_perf)
    >>> spec['deps']
    ('path',)
    >>> spec['extras']
    ('testing',)
    """
    yield 'name', (first_line(_func.__doc__) or _func.__name__)
    with contextlib.suppress(AttributeError):
        yield 'extras', freeze(_func.extras)
    with contextlib.suppress(AttributeError):
        yield 'deps', freeze(_func.deps)
    with contextlib.suppress(AttributeError):
        yield 'control', _func.control
    _header, _sep, _body_ind = inspect.getsource(_func).partition(':\n')
    _body = textwrap.dedent(_body_ind)
    warmup, sep, exercise = _body.rpartition('# end warmup')
    if warmup:
        yield 'warmup', warmup
    yield 'exercise', exercise


class Experiment(pytest.Item):
    _instances: 'List[Experiment]' = []
    results = None

    def __init__(self, name, parent, spec):
        super().__init__(name, parent)
        self.spec = spec
        self.command = assign_params(runner.Command, spec)()
        Experiment._instances.append(self)

    def runtest(self):
        self.results = self.runner.run(self.command)

    @property
    def config_params(self):
        return {
            key.partition('perf_')[-1]: value
            for key, value in vars(self.config.known_args_namespace).items()
            if value is not None
            if key.startswith('perf_')
        }

    @property
    def runner(self) -> runner.BenchmarkRunner:
        params = {**self.spec, **self.config_params}
        return assign_params(runner_factory, params)()

    def reportinfo(self):
        return self.fspath, 0, self.name

    def __str__(self):
        return f'{self.name}: {self.results}'

    def __bool__(self):
        return hasattr(self, 'results')
