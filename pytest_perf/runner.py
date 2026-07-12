from __future__ import annotations

import contextlib
import re
import subprocess
import sys
import tempfile
from collections.abc import Iterable
from datetime import timedelta
from typing import Any

import pip_run
import tempora
from jaraco.compat.py38 import r_fix
from jaraco.text import strip_ansi


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
    def delta(self) -> timedelta:
        return self.experiment - self.control

    @property
    def variance(self) -> float:
        try:
            return self.delta / self.control
        except ZeroDivisionError:
            return float('inf') if self.delta else 0

    @property
    def significant(self) -> bool:
        return self.variance > self.tolerance

    @property
    def experiment(self) -> timedelta:
        return self._parse_timeit_duration(self.experiment_text)

    @property
    def control(self) -> timedelta:
        return self._parse_timeit_duration(self.control_text)

    @staticmethod
    def _parse_timeit_duration(time: str) -> timedelta:
        return tempora.parse_timedelta(time)

    def __str__(self) -> str:
        return f'{self.experiment} (+{self.delta}, {self.variance:.0%})'

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
