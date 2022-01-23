import json
import re
import subprocess
import sys
from hashlib import md5
from itertools import chain
from pathlib import Path
from typing import Iterator, List
from urllib.request import urlopen

import pytest

from pytest_perf.runner import BenchmarkRunner, Command, local_package, upstream_package

HERE = Path(__file__).parent
DOWNLOADS = HERE / ".downloads"


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
        ]
    ],
)
def test_benchmark_runner(target, baseline, extras, command):
    package, version = target
    url, control = baseline
    cmd = Command(command)

    for dist in download_dists(package, version):
        runner = BenchmarkRunner(extras, (), control, str(dist), url)
        runner.run(cmd)


# --- Helper Functions ---


def download_dists(package: str, version: str) -> List[Path]:
    """Either use cached dist file or download it from PyPI"""
    DOWNLOADS.mkdir(exist_ok=True)

    distributions = retrieve_pypi_dist_metadata(package, version)
    filenames = {dist["filename"] for dist in distributions}

    # Remove old files to prevent cache to grow indefinitely
    canonical = canonicalize_name(package)
    names = [package, canonical, canonical.replace("-", "_")]
    for file in chain.from_iterable(DOWNLOADS.glob(f"{n}*") for n in names):
        if file.name not in filenames:
            file.unlink()

    dist_files = []
    for dist in retrieve_pypi_dist_metadata(package, version):
        dest = DOWNLOADS / dist["filename"]
        if not dest.exists():
            download(dist["url"], dest, dist["md5_digest"])
        dist_files.append(dest)

    return dist_files


def retrieve_pypi_dist_metadata(package: str, version: str) -> Iterator[dict]:
    # https://warehouse.pypa.io/api-reference/json.html
    id_ = f"{package}/{version}"
    with urlopen(f"https://pypi.org/pypi/{id_}/json") as f:
        metadata = json.load(f)

    if metadata["info"]["yanked"]:
        raise ValueError(f"Release for {package} {version} was yanked")

    version = metadata["info"]["version"]
    for dist in metadata["releases"][version]:
        if any(dist["filename"].endswith(ext) for ext in (".tar.gz", ".whl")):
            yield dist


def canonicalize_name(name: str) -> str:
    # PEP 503.
    return re.sub(r"[-_.]+", "-", name).lower()


def download(url: str, dest: Path, md5_digest: str) -> Path:
    with urlopen(url) as f:
        data = f.read()

    assert md5(data).hexdigest() == md5_digest

    with open(dest, "wb") as f:
        f.write(data)

    assert dest.exists()

    return dest
