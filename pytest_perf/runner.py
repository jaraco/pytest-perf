import sys
import re
import subprocess
import contextlib

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
        return self.delta / self.control

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

    def __init__(self, extras=None):
        spec = f'[{extras}]' if extras else ''
        self.stack = contextlib.ExitStack()
        self.baseline_env = self._setup_env(upstream_url(spec))
        self.local_env = self._setup_env(f'.{spec}')

    def _setup_env(self, deps):
        target = self.stack.enter_context(pip_run.deps.load(deps))
        return pip_run.launch._setup_env(target)

    def run(self, cmd: Command):
        local = self.eval(cmd, env=self.local_env)
        benchmark = self.eval(cmd, env=self.baseline_env)
        return Result(benchmark, local)

    def eval(self, cmd, **kwargs):
        out = subprocess.check_output(cmd, **_text, **kwargs)
        val = re.search(r'([0-9.]+ \w+) per loop', out).group(1)
        return val


def upstream_url(extras=''):
    """
    >>> upstream_url()
    'pytest-perf@git+https://github.com/jaraco/pytest-perf'
    """
    cmd = ['git', 'remote', 'get-url', 'origin']
    origin = subprocess.check_output(cmd, **_text).strip()
    base, sep, name = origin.rpartition('/')
    return f'{name}{extras}@git+{origin}'
