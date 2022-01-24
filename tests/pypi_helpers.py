import json
import re
from hashlib import md5
from itertools import chain
from pathlib import Path
from typing import Iterator, List
from urllib.request import urlopen


HERE = Path(__file__).parent
DOWNLOADS = HERE / ".downloads"


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
