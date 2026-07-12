"""
Prototype of a reusable pytest plugin providing a ``require_checkout``
fixture that skips a test when the project is not a git checkout with
an 'origin' remote (jaraco/pytest-perf#6).

A doctest opts in with a single line::

    >>> getfixture('require_checkout')

Intended to graduate to a shared library (e.g. jaraco.test) once proven.
"""

import subprocess

import pytest
from jaraco.context import ExceptionTrap


@ExceptionTrap((OSError, subprocess.CalledProcessError)).passes
def has_origin():
    """
    Is the project a git checkout with an 'origin' remote?
    """
    cmd = ['git', 'remote', 'get-url', 'origin']
    subprocess.run(cmd, capture_output=True, check=True)


@pytest.fixture
def require_checkout():
    """
    Skip the test unless a checkout with an 'origin' remote is present.
    """
    has_origin() or pytest.skip("requires a repo checkout with an 'origin' remote")
