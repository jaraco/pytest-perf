import sys
import re
import subprocess
import contextlib

import pip_run


_text = dict(text=True) if sys.version_info > (3, 7) else dict(universal_newlines=True)


class Command(list):
    def __init__(self, exercise='pass', warmup='pass'):
        self[:] = [
            sys.executable,
            '-m',
            'timeit',
            '--setup',
            warmup,
            '--',
            exercise,
        ]


class BenchmarkRunner:
    """
    >>> br = BenchmarkRunner()
    >>> br.run(Command('import time; time.sleep(0.01)'))
    ('...', '...')
    """

    def __init__(self):
        self.baseline_env = self._setup_env()

    def _setup_env(self):
        self.stack = contextlib.ExitStack()
        target = self.stack.enter_context(pip_run.deps.load(upstream_url()))
        return pip_run.launch._setup_env(target)

    def run(self, cmd: Command):
        local = self.eval(cmd)
        benchmark = self.eval(cmd, env=self.baseline_env)
        return benchmark, local

    def eval(self, cmd, **kwargs):
        out = subprocess.check_output(cmd, **_text, **kwargs)
        val = re.search(r'([0-9.]+ \w+) per loop', out).group(1)
        return val


def upstream_url():
    """
    >>> upstream_url()
    'git+https://github.com/jaraco/pytest-perf'
    """
    cmd = ['git', 'remote', 'get-url', 'origin']
    origin = subprocess.check_output(cmd, **_text).strip()
    return f'git+{origin}'
