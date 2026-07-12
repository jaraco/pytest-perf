import subprocess

import pytest

from pytest_perf.runner import _git_origin

# Doctests that shell out to git and so require a git checkout with an
# 'origin' remote (jaraco/pytest-perf#6).
needs_git = {
    'pytest_perf.runner.BenchmarkRunner',
    'pytest_perf.runner.upstream_url',
}


def git_available():
    """
    Is the project a git checkout with an 'origin' remote?
    """
    try:
        subprocess.run(_git_origin, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def pytest_collection_modifyitems(items):
    if git_available():
        return
    skip = pytest.mark.skip(reason="git checkout with 'origin' remote unavailable")
    for item in items:
        if item.name in needs_git:
            item.add_marker(skip)
