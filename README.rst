.. image:: https://img.shields.io/pypi/v/pytest-perf.svg
   :target: https://pypi.org/project/pytest-perf

.. image:: https://img.shields.io/pypi/pyversions/pytest-perf.svg

.. image:: https://github.com/jaraco/pytest-perf/actions/workflows/main.yml/badge.svg
   :target: https://github.com/jaraco/pytest-perf/actions?query=workflow%3A%22tests%22
   :alt: tests

.. image:: https://img.shields.io/endpoint?url=https://raw.githubusercontent.com/astral-sh/ruff/main/assets/badge/v2.json
    :target: https://github.com/astral-sh/ruff
    :alt: Ruff

.. .. image:: https://readthedocs.org/projects/PROJECT_RTD/badge/?version=latest
..    :target: https://PROJECT_RTD.readthedocs.io/en/latest/?badge=latest

.. image:: https://img.shields.io/badge/skeleton-2026-informational
   :target: https://blog.jaraco.com/skeleton

Run performance tests against the mainline code.

``pytest-perf`` measures whether a change makes code slower by
benchmarking the working copy (the *experiment*) against the mainline
(the *control*) and reporting the difference. It installs each version
into its own environment, runs the same exercise against both, and
fails only when a regression exceeds the tolerance.

Installation
============

Add ``pytest-perf`` to your project's test dependencies. For example,
in ``pyproject.toml``::

    [project.optional-dependencies]
    test = [
        "pytest-perf",
    ]

The package registers a pytest plugin automatically; no further
configuration is required.

Writing performance tests
=========================

Create a Python module anywhere pytest will collect it (for example
``exercises.py`` at the project root). Two conventions drive collection:

- The plugin only inspects modules whose source contains the text
  ``pytest_perf``. Importing something from the package —
  ``from pytest_perf.deco import ...`` — is enough, but even a bare
  comment mentioning ``pytest_perf`` qualifies the module.
- Within such a module, every function whose name contains ``perf``
  (or ``import_time``; see `Import latency`_) becomes a benchmark.

A benchmark function is not executed directly. Instead, its source is
split into two parts at a ``# end warmup`` comment: the *warmup* runs
once as setup, and the *exercise* (everything after the comment) is the
code that gets timed. Both parts are handed to the ``timeit`` module::

    def dict_construction_perf():
        "constructing a dict"
        from itertools import product

        pairs = list(product(range(100), range(100)))  # end warmup

        dict(pairs)

Here the imports and data setup run once as warmup, and only
``dict(pairs)`` is timed. If a function has no ``# end warmup`` marker,
its whole body is the exercise.

The first line of the docstring, when present, names the benchmark in
the report; otherwise the function name is used.

Decorators
==========

The ``pytest_perf.deco`` module supplies decorators to control how the
benchmark's environments are built:

``@deps('name', ...)``
    Install additional distributions into both environments before
    running the exercise. Use this when the exercise imports a package
    that isn't otherwise a dependency.

``@extras('name', ...)``
    Install the named `extras
    <https://packaging.python.org/en/latest/specifications/dependency-specifiers/#extras>`_
    of the project (e.g. ``testing``) into both environments.

``@control('rev')``
    Pin the control environment to a specific git revision (tag,
    branch, or commit) instead of the mainline head. Handy for measuring
    the cumulative change since a released version.

::

    from pytest_perf.deco import control, deps, extras

    @extras('testing')
    @deps('path')
    def deps_and_extras_perf():
        "with deps and extras"
        import path
        import pytest  # end warmup

        assert type(pytest) is type(path)

    @control('v0.9.2')
    def diff_from_oh_nine_two_perf():
        pass

See the ``exercises.py`` module in this repository for more examples.

Running the tests
=================

Run pytest as usual; the benchmarks are collected and executed
alongside your other tests::

    pytest

Building two isolated environments and installing into them takes time,
so restrict a run to the perf module when iterating::

    pytest exercises.py

Results are printed in a ``perf`` section of the terminal summary, one
line per benchmark, showing the experiment timing, the delta from the
control, and the percentage change::

    ------------------------------ perf ------------------------------
    exercises.py:simple test: 38.1 nsec (+3.9 nsec, 11%)

A benchmark fails only when the slowdown exceeds the tolerance
(a 100% increase by default), so ordinary run-to-run noise won't break
your build.

Options
=======

Two command-line options adjust what is compared:

``--perf-baseline URL``
    The git repository to use as the control. Defaults to the ``origin``
    remote of the local repository.

``--perf-target DIR``
    The directory or distribution file to use as the experiment.
    Defaults to the current project (``.``).

Import latency
==============

``timeit`` cannot measure the cost of importing a module, because after the
first loop the module is cached in ``sys.modules`` and subsequent loops only
measure the cache lookup. To measure import latency instead, name the function
with ``import_time`` (in place of ``perf``) and let its body perform the
import::

    def check_import_time():
        import importlib_metadata

Such a function is traced with ``python -X importtime`` in a fresh interpreter
(sampled a few times, reporting the fastest) rather than timed with ``timeit``,
capturing the real cold-import cost against both the control and the experiment.

Import latency cannot be measured on interpreters that don't emit an
``-X importtime`` trace (such as PyPy); those benchmarks are skipped.

Design
======

``pytest-perf`` works by creating two installs, the control and the experiment, and measuring the performance of some python code against each.

Under the hood, it uses ``pip-run`` to install from the upstream main branch (e.g. https://github.com/jaraco/pytest-perf) for the control and from ``.`` for the experiment. It then runs each of the experiments against each of the enviroments.
