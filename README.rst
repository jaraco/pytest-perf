.. image:: https://img.shields.io/pypi/v/pytest-perf.svg
   :target: `PyPI link`_

.. image:: https://img.shields.io/pypi/pyversions/pytest-perf.svg
   :target: `PyPI link`_

.. _PyPI link: https://pypi.org/project/pytest-perf

.. image:: https://github.com/jaraco/pytest-perf/workflows/tests/badge.svg
   :target: https://github.com/jaraco/pytest-perf/actions?query=workflow%3A%22tests%22
   :alt: tests

.. image:: https://img.shields.io/badge/code%20style-black-000000.svg
   :target: https://github.com/psf/black
   :alt: Code style: Black

.. .. image:: https://readthedocs.org/projects/skeleton/badge/?version=latest
..    :target: https://skeleton.readthedocs.io/en/latest/?badge=latest

.. image:: https://img.shields.io/badge/skeleton-2021-informational
   :target: https://blog.jaraco.com/skeleton

Run performance tests against the mainline code.

To use it, include pytest-perf in the test dependencies for your project, then create some Python module in your package. The plugin will include any module that contains the text "pytest_perf" and will run performance tests on each function containing "perf" in the name.

Tests don't execute the module directly, but instead parse out the code of the function in two parts, the warmup and the test, separated by a "# end warmup" comment, and then passes those to the ``timeit`` module.

See the ``exercises.py`` module for example usage.
