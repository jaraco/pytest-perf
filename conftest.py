"""
Prototype of a reusable pytest plugin to skip doctests that require a
git checkout when none is available (jaraco/pytest-perf#6).

A doctest opts in by including the marker string "requires git" anywhere
in its docstring. When the project is not a git checkout with an 'origin'
remote, such doctests are skipped rather than failing.

Intended to graduate to a shared library (e.g. jaraco.test) once proven.
"""

import subprocess

import pytest

from pytest_perf.runner import _git_origin

MARKER = 'requires git'


def git_available():
    """
    Is the project a git checkout with an 'origin' remote?
    """
    try:
        subprocess.run(_git_origin, capture_output=True, check=True)
    except (OSError, subprocess.CalledProcessError):
        return False
    return True


def _requires_git(item):
    docstring = getattr(getattr(item, 'dtest', None), 'docstring', '') or ''
    return MARKER in docstring.lower()


def pytest_collection_modifyitems(items):
    if git_available():
        return
    skip = pytest.mark.skip(reason=f"doctest {MARKER!r}, but none is available")
    for item in filter(_requires_git, items):
        item.add_marker(skip)
