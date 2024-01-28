import sys
import re
import subprocess
import contextlib
import tempfile

import pip_run
import tempora


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

    def __init__(self, extras=(), deps=(), control=None):
        spec = f'[{",".join(extras)}]' if extras else ''
        self.stack = contextlib.ExitStack()
        self.control_env = self._setup_env(upstream_url(spec, control), *deps)
        self.experiment_env = self._setup_env(f'.{spec}', *deps)

    def _setup_env(self, *deps):
        target = self.stack.enter_context(pip_run.deps.load(*deps))
        return pip_run.launch._setup_env(target)

    def run(self, cmd: Command):
        experiment = self.eval(cmd, env=self.experiment_env)
        control = self.eval(cmd, env=self.control_env)
        return Result(control, experiment)

    def eval(self, cmd, **kwargs):
        with tempfile.TemporaryDirectory() as empty:
            out = subprocess.check_output(
                cmd, cwd=empty, encoding='utf-8', text=True, **kwargs
            )
        val = re.search(r'([0-9.]+ \w+) per loop', out).group(1)
        return val


def upstream_url(extras='', control=None):
    """
    >>> upstream_url()
    'pytest-perf@git+https://github.com/jaraco/pytest-perf'
    >>> upstream_url(extras='[tests]', control='v0.9.2')
    'pytest-perf[tests]@git+https://github.com/jaraco/pytest-perf@v0.9.2'
    """
    cmd = ['git', 'remote', 'get-url', 'origin']
    origin = subprocess.check_output(cmd, encoding='utf-8', text=True).strip()
    base, sep, name = origin.rpartition('/')
    rev = f'@{control}' if control else ''
    return f'{name}{extras}@git+{origin}{rev}'
