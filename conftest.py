"""
Prototype of a reusable pytest plugin providing a ``require_repo``
fixture that skips a test when the project is not a git checkout with
an 'origin' remote (jaraco/pytest-perf#6).

A doctest opts in with a single line::

    >>> getfixture('require_repo')

Intended to graduate to a shared library (e.g. jaraco.test) once proven.
"""

import subprocess

import pytest

from pytest_perf.runner import _git_origin


def git_available():
    """
    Is the project a git checkout with an 'origin' remote?
    """
    try:
        subprocess.run(_git_origin, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


@pytest.fixture
def require_repo():
    """
    Skip the test unless a git checkout with an 'origin' remote is present.
    """
    if not git_available():
        pytest.skip("requires a git checkout with an 'origin' remote")
