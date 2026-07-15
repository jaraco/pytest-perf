from __future__ import annotations

import contextlib
import functools
import importlib
import inspect
import re
import textwrap
from collections.abc import Iterator
from pathlib import Path
from types import ModuleType
from typing import Any

import pytest
from jaraco.context import suppress
from jaraco.functools import apply, assign_params, pass_none
from more_itertools import peekable
from packaging.version import Version

from pytest_perf import runner


def pytest_addoption(parser: pytest.Parser) -> None:
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


def _collect_file_pytest7(parent: pytest.Collector, file_path: Path) -> File | None:
    if file_path.suffix == '.py' and 'pytest_perf' in file_path.read_text(
        encoding='utf-8'
    ):
        return File.from_parent(parent, path=file_path)
    return None


def _collect_file_pytest6(parent: pytest.Collector, path: Any) -> File | None:
    if path.basename.endswith('.py') and 'pytest_perf' in path.read_text(
        encoding='utf-8'
    ):
        return File.from_parent(parent, fspath=path)
    return None


old_pytest = Version(pytest.__version__) < Version('7')
pytest_collect_file = suppress(UnicodeDecodeError)(
    _collect_file_pytest6 if old_pytest else _collect_file_pytest7
)


def pytest_terminal_summary(
    terminalreporter: pytest.TerminalReporter, config: pytest.Config
) -> None:
    items = peekable(filter(None, Experiment._instances))
    items and terminalreporter.section('perf')  # type: ignore[func-returns-value] # side effect
    for line in map(str, items):
        terminalreporter.write_line(line)


def pytest_sessionfinish() -> None:
    """
    Clear the runner factory to tear down any BenchmarkRunners.
    """
    runner_factory.cache_clear()


class File(pytest.File):
    def collect(self) -> Iterator[Experiment]:
        return (
            Experiment.from_parent(self, name=f'{self.name}:{spec["name"]}', spec=spec)
            for spec in map(spec_from_func, funcs_from_name(self.path))
        )


runner_factory = functools.lru_cache()(runner.BenchmarkRunner)


@suppress(Exception)
def load_module(path: Path) -> ModuleType:
    spec = importlib.util.spec_from_file_location(path.stem, path)
    mod = importlib.util.module_from_spec(spec)  # type: ignore[arg-type] # suppressed
    spec.loader.exec_module(mod)  # type: ignore[union-attr] # suppressed
    return mod


def funcs_from_name(path: Path) -> Iterator[Any]:
    mod = load_module(path)
    return (
        getattr(mod, name)
        for name in dir(mod)
        if re.search(r'(\b|_)(perf|import_time)(\b|_)', name)
    )


@pass_none
def first_line(text: str) -> str | None:
    lines = (line.strip() for line in text.splitlines())
    return next(lines, None)


freeze = pass_none(tuple)


@apply(dict)
def spec_from_func(_func: Any) -> Iterator[tuple[str, Any]]:
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

    A function whose name signals ``import_time`` is measured as an
    import-time exercise (jaraco/pytest-perf#12); its whole body is the
    exercise:

    >>> spec = spec_from_func(exercises.import_time_check)
    >>> spec['import_time']
    True
    >>> spec['exercise'].strip()
    'import pytest_perf  # noqa: F401'
    """
    yield 'name', (first_line(_func.__doc__) or _func.__name__)
    if re.search(r'(\b|_)import_time(\b|_)', _func.__name__):
        yield 'import_time', True
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
    _instances: list[Experiment] = []
    results: runner.Result | None = None

    def __init__(self, name: str, parent: pytest.Collector, spec: dict[str, Any]):
        super().__init__(name, parent)
        self.spec = spec
        self.command = assign_params(runner.Command, spec)()
        Experiment._instances.append(self)

    def runtest(self) -> None:
        try:
            self.results = self.runner.run(self.command)
        except runner.ImportTimeUnsupported as exc:
            pytest.skip(str(exc))

    @property
    def config_params(self) -> dict[str, Any]:
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

    def reportinfo(self) -> tuple[Any, int, str]:
        return self.fspath, 0, self.name

    def __str__(self) -> str:
        return f'{self.name}: {self.results}'

    def __bool__(self) -> bool:
        return self.results is not None
