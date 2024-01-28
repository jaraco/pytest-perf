v0.14.0
=======

Features
--------

- Prefer spec_from_file_location when loading perf functions.


Bugfixes
--------

- Suppress UnicodeDecodeError when a non-standard encoding is encountered.


v0.13.1
=======

#8: Added a project description to the metadata.

v0.13.0
=======

#4: Allow command line parameters to override ``target``
and ``baseline``.

v0.12.1
=======

#7: Fixed test discovery regression on Pytest 7 behavior.

v0.12.0
=======

#5: Added compatibility for Pytest 7.

v0.11.0
=======

Require Python 3.7.

v0.10.1
=======

#2: Fixed isolation issue with exercise runner.

v0.10.0
=======

Add 'control' directive to override the control revision.

v0.9.2
======

Rely on lower level ``importlib.util`` functions to reduce
the effect of loading a module. Require that modules
contain 'pytest_perf' in them to be loaded.

v0.9.1
======

Suppress exceptions when modules cannot be imported.

v0.9.0
======

#1: Instead of an ini file, this plugin now discovers the
tests from any function with "perf" in the function name.
See "exercises.py" in this repo for a demo of the syntax.

v0.8.0
======

Add support for 'deps'.

v0.7.0
======

Improved error handling and report formatting.

v0.6.2
======

Fix bug where stack was overwritten, exiting the baseline_env
early.

v0.6.1
======

Bump to pip-run 8.5 to avoid pkg_resources mucking with
the sys.path.

v0.6.0
======

Renamed plugin to simply 'perf' to match convention.

v0.5.1
======

Fixed bug where ``shutil.rmtree`` would fail during pip-run
teardowns when BenchmarkRunners would linger until interpreter
teardown.

v0.5.0
======

Runner now creates a separate environment for the local package,
avoiding relying on the environment under test, thus providing a
better comparison.

v0.4.0
======

Now ``extras`` can be specified for each experiment.

v0.3.0
======

Now reports include an indication of how much variance was observed
between the control and experiment.

v0.2.0
======

Added pytest plugin with reporting support.

v0.1.0
======

Initial release with BenchmarkRunner.
