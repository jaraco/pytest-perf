import subprocess
import sys

import pytest

from pytest_perf.runner import BenchmarkRunner, Command, local_package, upstream_package

from .pypi_helpers import download_dists


@pytest.mark.parametrize(
    "package, version, extras",
    [
        ("build", "0.7.0", ""),
        ("build", "0.7.0", "[virtualenv]"),
    ],
)
def test_local_package(package, version, extras, tmp_path):
    # Ensure local packages can be installed with/without extras
    for dist in download_dists(package, version):
        with local_package(str(dist)) as pkg:
            installable = f"{pkg}{extras}"
            cmd = [
                sys.executable,
                "-m",
                "pip",
                "install",
                "-t",
                str(tmp_path),
                installable,
            ]
            subprocess.run(cmd, check=True)


@pytest.mark.parametrize(
    "url, rev, extras",
    [
        ("https://github.com/pypa/setuptools_scm.git", "v6.0.0", ""),
        ("https://github.com/pypa/setuptools_scm", "v6.4.2", "[toml]"),
        (None, None, ""),
    ],
)
def test_upstream_package(url, rev, extras, tmp_path):
    # Ensure remote VCS packages can be installed with/without extras
    with upstream_package(url, rev) as pkg:
        installable = f"{pkg}{extras}"
        cmd = [
            sys.executable,
            "-m",
            "pip",
            "install",
            "-t",
            str(tmp_path),
            installable,
        ]
        subprocess.run(cmd, check=True)


@pytest.mark.parametrize(
    "target, baseline, extras, command",
    [
        [
            ("setuptools_scm", "6.0.0"),
            ("https://github.com/pypa/setuptools_scm.git", "v6.4.2"),
            ["toml"],
            "import setuptools_scm",
        ],
        [
            ("jaraco.context", "3.0.0"),
            ("https://github.com/jaraco/jaraco.context", "v4.1.1"),
            [],
            "from jaraco import context",
        ],
    ],
)
def test_benchmark_runner(target, baseline, extras, command):
    package, version = target
    url, control = baseline
    cmd = Command(command)

    for dist in download_dists(package, version):
        runner = BenchmarkRunner(extras, (), control, str(dist), url)
        runner.run(cmd)
