from __future__ import annotations

import contextlib
import decimal
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from typing import Any

import pip_run
import tempora
from jaraco.compat.py38 import r_fix
from jaraco.text import strip_ansi

_units = (1e0, 'nsec'), (1e3, 'usec'), (1e6, 'msec'), (1e9, 'sec')


def _format_duration(nanoseconds: decimal.Decimal, *, signed: bool = False) -> str:
    """
    Render a duration (given in nanoseconds) using timeit's units.

    >>> _format_duration(decimal.Decimal('34.2'))
    '34.2 nsec'
    >>> _format_duration(decimal.Decimal('1600'))
    '1.6 usec'
    >>> _format_duration(decimal.Decimal('12300000'))
    '12.3 msec'
    >>> _format_duration(decimal.Decimal('0'))
    '0 nsec'

    Pass ``signed`` to prefix non-negative values with ``+``, for deltas.

    >>> _format_duration(decimal.Decimal('3.9'), signed=True)
    '+3.9 nsec'
    >>> _format_duration(decimal.Decimal('-3.9'), signed=True)
    '-3.9 nsec'
    """
    value = float(nanoseconds)
    factor, unit = _units[0]
    for factor, unit in _units:
        if abs(value) < factor * 1000:
            break
    sign = '+' if signed and value >= 0 else ''
    return f'{sign}{value / factor:.3g} {unit}'


class Command(list):
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


class Result:
    # by default, anything under 100% increase is not significant
    tolerance = 1.0

    def __init__(self, control: str, experiment: str) -> None:
        self.control_text = control
        self.experiment_text = experiment

    @property
    def delta(self) -> decimal.Decimal:
        return self.experiment - self.control

    @property
    def variance(self) -> float:
        if not self.control:
            return float('inf') if self.delta else 0.0
        return float(self.delta / self.control)

    @property
    def significant(self) -> bool:
        return self.variance > self.tolerance

    @property
    def experiment(self) -> decimal.Decimal:
        return self._parse_timeit_duration(self.experiment_text)

    @property
    def control(self) -> decimal.Decimal:
        return self._parse_timeit_duration(self.control_text)

    @staticmethod
    def _parse_timeit_duration(time: str) -> decimal.Decimal:
        # nanosecond precision matters when comparing sub-microsecond
        # timings; a timedelta would round it away. jaraco/pytest-perf#18
        return tempora.parse_nanoseconds(time)

    def __str__(self) -> str:
        return (
            f'{_format_duration(self.experiment)} '
            f'({_format_duration(self.delta, signed=True)}, {self.variance:.0%})'
        )

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
        with tempfile.TemporaryDirectory() as empty:
            out = subprocess.check_output(
                cmd, cwd=empty, encoding='utf-8', text=True, **kwargs
            )
        # Python 3.15+ colorizes timeit output when color is enabled (e.g.
        # FORCE_COLOR); strip escape sequences before parsing. jaraco/pytest-perf#20
        val = re.search(  # type: ignore[union-attr] # output always matches
            r'([0-9.]+ \w+) per loop', strip_ansi(out)
        ).group(1)
        return val


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
