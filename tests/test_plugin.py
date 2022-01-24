import pytest

from .pypi_helpers import download_dists


@pytest.mark.parametrize(
    "target, baseline, extras, test_code",
    [
        [
            ("setuptools_scm", "6.0.0"),
            ("https://github.com/pypa/setuptools_scm.git", "v6.4.2"),
            "toml",
            "import setuptools_scm",
        ],
        [
            ("jaraco.context", "3.0.0"),
            ("https://github.com/jaraco/jaraco.context", "v4.1.1"),
            "",
            "from jaraco import context",
        ],
    ],
)
def test_example(testdir, target, baseline, extras, test_code):
    """Make sure pytest-perf can be configured"""
    package, version = target
    url, control = baseline

    for dist in download_dists(package, version):
        args = ["--perf-target", str(dist), "--perf-baseline", url]
        test = f"""
        from pytest_perf.deco import extras, control

        @extras({extras!r})
        @control({control!r})
        def simple():
            {test_code}
        """
        testdir.makepyfile(test)
        result = testdir.runpytest(*args)
        result.assert_outcomes(errors=0)
