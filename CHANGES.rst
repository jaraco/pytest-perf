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
