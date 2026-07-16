from __future__ import annotations

import contextlib
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from typing import Any

import pip_run
import tempora
from jaraco.compat.py38 import r_fix
from jaraco.functools import signed
from jaraco.text import strip_ansi


class Command(list):
    """
    Build the argv to time an exercise with ``timeit``.

    >>> Command('dir()')[1:]
    ['-s', '-m', 'timeit', '--setup', 'pass', '--', 'dir()']
    """

    #: number of times to sample; the fastest is reported. ``timeit``
    #: loops internally, so a single sample suffices.
    samples = 1

    def __init__(self, exercise: str = 'pass', warmup: str = 'pass') -> None:
        self[:] = [
            sys.executable,
            '-s',
            '-m',
            'timeit',
            '--setup',
            warmup,
            '--',
            exercise,
        ]

    def parse(self, output: str) -> str:
        """
        Extract a timing (as a duration string) from ``timeit`` output.
        """
        # Python 3.15+ colorizes timeit output when color is enabled (e.g.
        # FORCE_COLOR); strip escape sequences before parsing. jaraco/pytest-perf#20
        return re.search(  # type: ignore[union-attr] # output always matches
            r'([0-9.]+ \w+) per loop', strip_ansi(output)
        ).group(1)


class ImportTimeUnsupported(Exception):
    """
    The interpreter emitted no ``-X importtime`` trace.

    PyPy (and other non-CPython interpreters) accept ``-X importtime``
    but produce no output, so import latency cannot be measured there.
    jaraco/pytest-perf#12
    """


class ImportTimeCommand(Command):
    """
    Build the argv to trace a cold import with ``-X importtime``.

    ``timeit`` is unsuitable for imports because the module is cached in
    ``sys.modules`` after the first loop, measuring only the cache hit.
    jaraco/pytest-perf#12

    >>> ImportTimeCommand('import json')[1:]
    ['-X', 'importtime', '-c', 'import json']
    """

    #: a cold import runs only once per process, so sample several
    #: processes and report the fastest.
    samples = 5

    def __init__(self, exercise: str = 'pass') -> None:
        self[:] = [sys.executable, '-X', 'importtime', '-c', exercise]

    def parse(self, output: str) -> str:
        r"""
        Extract the cumulative import time (microseconds) of the module
        imported last from a ``-X importtime`` trace.

        Interpreter start-up imports (``site`` and friends) complete
        before the ``-c`` exercise runs, so the final trace line is the
        module the exercise requested, and its cumulative time is the
        total cost of the import.

        >>> trace = '''
        ... import time: self [us] | cumulative | imported package
        ... import time:       656 |       2706 | site
        ... import time:       224 |       6174 | json'''
        >>> ImportTimeCommand().parse(trace)
        '6174 usec'

        An interpreter that emits no trace (e.g. PyPy) is reported as
        unsupported rather than yielding a bogus measurement:

        >>> ImportTimeCommand().parse('')
        Traceback (most recent call last):
        ...
        pytest_perf.runner.ImportTimeUnsupported: ...
        """
        cumulative = re.findall(r'import time:\s*\d+\s*\|\s*(\d+)', output)
        if not cumulative:
            raise ImportTimeUnsupported(
                "'-X importtime' produced no trace; "
                "this interpreter can't measure import latency"
            )
        return f'{cumulative[-1]} usec'


class Result:
    """
    Compare a control and experiment timing as produced by timeit.

    >>> r = Result('34.2 nsec', '38.1 nsec')
    >>> r.experiment
    Duration(Decimal('38.1'))
    >>> r.delta
    Duration(Decimal('3.9'))
    >>> r.significant
    False
    >>> print(r)
    38.1 nsec (+3.9 nsec, 11%)

    When the control rounds to zero, variance is infinite (or zero when
    nothing changed) rather than raising:

    >>> Result('0 nsec', '5 nsec').variance
    inf
    >>> Result('0 nsec', '0 nsec').variance
    0.0
    """

    # by default, anything under 100% increase is not significant
    tolerance = 1.0

    def __init__(self, control: str, experiment: str) -> None:
        self.control_text = control
        self.experiment_text = experiment

    @property
    def delta(self) -> tempora.Duration:
        return self.experiment - self.control

    @property
    def variance(self) -> float:
        try:
            return float(self.delta / self.control)
        except ArithmeticError:
            return float('inf') if self.delta else 0.0

    @property
    def significant(self) -> bool:
        return self.variance > self.tolerance

    @property
    def experiment(self) -> tempora.Duration:
        return self._parse_timeit_duration(self.experiment_text)

    @property
    def control(self) -> tempora.Duration:
        return self._parse_timeit_duration(self.control_text)

    @staticmethod
    def _parse_timeit_duration(time: str) -> tempora.Duration:
        # a Duration retains the sub-microsecond precision that a
        # timedelta would round away. jaraco/pytest-perf#18
        return tempora.Duration.parse(time)

    def __str__(self) -> str:
        delta = signed(str)(self.delta)
        return f'{self.experiment} ({delta}, {self.variance:.0%})'

    def __repr__(self) -> str:
        return f'Result({self.control_text!r}, {self.experiment_text!r})'


class BenchmarkRunner:
    """
    >>> getfixture('ensure_checkout')
    >>> br = BenchmarkRunner()
    >>> br.run(Command('import time; time.sleep(0.01)'))
    Result('...', '...')
    """

    def __init__(
        self,
        extras: Iterable[str] = (),
        deps: Iterable[str] = (),
        control: str | None = None,
    ) -> None:
        spec = f'[{",".join(extras)}]' if extras else ''
        self.stack = contextlib.ExitStack()
        self.control_env = self._setup_env(upstream_url(spec, control), *deps)
        self.experiment_env = self._setup_env(f'.{spec}', *deps)

    def _setup_env(self, *deps: str) -> Any:
        target = self.stack.enter_context(pip_run.deps.load(*deps))
        return pip_run.launch._setup_env(target)

    def run(self, cmd: Command) -> Result:
        experiment = self.eval(cmd, env=self.experiment_env)
        control = self.eval(cmd, env=self.control_env)
        return Result(control, experiment)

    def eval(self, cmd: Command, **kwargs: Any) -> str:
        samples = (self._sample(cmd, **kwargs) for _ in range(cmd.samples))
        return min(samples, key=tempora.Duration.parse)

    def _sample(self, cmd: Command, **kwargs: Any) -> str:
        with tempfile.TemporaryDirectory() as empty:
            out = subprocess.check_output(
                cmd,
                cwd=empty,
                encoding='utf-8',
                text=True,
                # -X importtime writes its trace to stderr
                stderr=subprocess.STDOUT,
                **kwargs,
            )
        return cmd.parse(out)


_git_origin = ['git', 'remote', 'get-url', 'origin']


def upstream_url(extras: str = '', control: str | None = None) -> str:
    """
    >>> getfixture('ensure_checkout')
    >>> upstream_url()
    'pytest-perf@git+https://github.com/jaraco/pytest-perf'
    >>> upstream_url(extras='[tests]', control='v0.9.2')
    'pytest-perf[tests]@git+https://github.com/jaraco/pytest-perf@v0.9.2'

    Exercise some other circumstances by faking the git call.

    >>> fp = getfixture('fp')
    >>> _ = fp.register(_git_origin, "ssh://github.com/pypa/setuptools")
    >>> upstream_url()
    'setuptools@git+ssh://github.com/pypa/setuptools'

    >>> _ = fp.register(_git_origin, "git@github.com:pypa/setuptools.git")
    >>> upstream_url(control="v69.0.1")
    'setuptools@git+ssh://git@github.com/pypa/setuptools.git@v69.0.1'
    """
    origin = subprocess.check_output(_git_origin, encoding='utf-8', text=True).strip()
    origin_url = _ensure_url(origin)
    base, sep, name = origin.rpartition('/')
    clean_name = r_fix(name).removesuffix('.git')
    rev = f'@{control}' if control else ''
    return f'{clean_name}{extras}@git+{origin_url}{rev}'


def _ensure_url(origin: str) -> str:
    """
    Convert any implied protocol origins to a SSH URL.

    >>> _ensure_url("git@github.com:jaraco/tempora.git")
    'ssh://git@github.com/jaraco/tempora.git'
    >>> _ensure_url("github.com:jaraco/tempora")
    'ssh://github.com/jaraco/tempora'
    """
    if '://' in origin:
        return origin
    host, path = origin.split(':', 1)
    return f'ssh://{host}/{path}'
