import os
import sys
import re
import subprocess
import contextlib
import tempfile
from typing import ContextManager, Iterable, Iterator, List, Optional

import pip_run
import tempora

_text = dict(text=True) if sys.version_info > (3, 7) else dict(universal_newlines=True)


class Command(list):
    def __init__(self, exercise='pass', warmup='pass'):
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

    def __init__(self, control, experiment):
        self.control_text = control
        self.experiment_text = experiment

    @property
    def delta(self):
        return self.experiment - self.control

    @property
    def variance(self):
        try:
            return self.delta / self.control
        except ZeroDivisionError:
            return float('inf') if self.delta else 0

    @property
    def significant(self):
        return self.variance > self.tolerance

    @property
    def experiment(self):
        return self._parse_timeit_duration(self.experiment_text)

    @property
    def control(self):
        return self._parse_timeit_duration(self.control_text)

    @staticmethod
    def _parse_timeit_duration(time):
        return tempora.parse_timedelta(time)

    def __str__(self):
        return f'{self.experiment} (+{self.delta}, {self.variance:.0%})'

    def __repr__(self):
        return f'Result({self.control_text!r}, {self.experiment_text!r})'


class BenchmarkRunner:
    """
    >>> br = BenchmarkRunner()
    >>> br.run(Command('import time; time.sleep(0.01)'))
    Result('...', '...')
    """

    def __init__(
        self,
        extras: Iterable[str] = (),
        deps: Iterable[str] = (),
        control: Optional[str] = None,
        target: str = '.',
        baseline: Optional[str] = None,
    ):
        self.spec = f'[{",".join(extras)}]' if extras else ''
        self.stack = contextlib.ExitStack()
        self.control_env = self._setup_env(upstream_package(baseline, control), *deps)
        self.experiment_env = self._setup_env(local_package(target), *deps)

    def _setup_env(self, install_context: ContextManager[str], *deps: str):
        with install_context as package:
            # Close the install context as soon as the package is installed
            # to avoid baseline <=> target interference.
            install_item = f"{package}{self.spec}"
            target = self.stack.enter_context(pip_run.deps.load(install_item, *deps))
        return pip_run.launch._setup_env(target)

    def run(self, cmd: Command) -> Result:
        try:
            experiment = self.eval(cmd, env=self.experiment_env)
            control = self.eval(cmd, env=self.control_env)
            return Result(control, experiment)
        finally:
            self.stack.close()

    def eval(self, cmd: List[str], **kwargs) -> str:
        with tempfile.TemporaryDirectory() as empty:
            out = subprocess.check_output(  # type: ignore
                cmd, cwd=empty, **_text, **kwargs
            )
        val = re.search(r'([0-9.]+ \w+) per loop', out).group(1)  # type: ignore
        return val


def upstream_url() -> str:
    """
    >>> upstream_url()
    'https://github.com/jaraco/pytest-perf'
    """
    cmd = ['git', 'remote', 'get-url', 'origin']
    return subprocess.check_output(cmd, **_text).strip()  # type: ignore


@contextlib.contextmanager
def upstream_package(
    url: Optional[str] = None, control: Optional[str] = None
) -> Iterator[str]:
    """Clone the upstream URL to be used as a local package.
    This avoids the need of knowing the package name to install optional dependencies.
    """
    url = url or upstream_url()
    rev: List[str] = ['--branch', control] if control else []
    with tempfile.TemporaryDirectory() as tmp:
        cmd = ['git', 'clone', *rev, url, str(tmp)]
        subprocess.run(cmd, check=True, **_text)  # type: ignore
        with local_package(tmp) as target:
            yield target


@contextlib.contextmanager
def local_package(target: str) -> Iterator[str]:
    """Installation context for local package to workaround ``pip`` limitations
    (``pip`` only allow extras for a distribution archive or ``.``,
    not local directories in general).

    The installation context will ``chdir`` into an directory from where the
    installation should take place and bind the name of the installable item
    to the target of the ``with ... as`` clause.
    """
    if target != "." and os.path.isdir(target):
        _orig_dir = os.getcwd()
        os.chdir(target)
        try:
            yield "."
        finally:
            os.chdir(_orig_dir)
    else:
        yield target
