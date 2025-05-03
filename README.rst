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

.. image:: https://img.shields.io/badge/skeleton-2025-informational
   :target: https://blog.jaraco.com/skeleton

Run performance tests against the mainline code.

Usage
=====

To use it, include pytest-perf in the test dependencies for your project, then create some Python module in your package. The plugin will include any module that contains the text "pytest_perf" and will run performance tests on each function containing "perf" in the name.

Tests don't execute the module directly, but instead parse out the code of the function in two parts, the warmup and the test, separated by a "# end warmup" comment, and then passes those to the ``timeit`` module.

See the ``exercises.py`` module for example usage.

Design
======

``pytest-perf`` works by creating two installs, the control and the experiment, and measuring the performance of some python code against each.

Under the hood, it uses ``pip-run`` to install from the upstream main branch (e.g. https://github.com/jaraco/pytest-perf) for the control and from ``.`` for the experiment. It then runs each of the experiments against each of the enviroments.
