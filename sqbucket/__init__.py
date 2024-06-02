from typing import Sequence, Literal
from importlib.metadata import entry_points
from platform import machine
import requests
import tempfile
import shutil
import json
import io
import csv
import os

from .config import cfg, platform

CHUNK_SIZE = 8 * 1024 * 1024
SQLITE_URL = "https://www.sqlite.org/"
SQLITE_LIST_URL = f"{SQLITE_URL}download.html"
SQLPKG_TARGET = "nalgeon/sqlpkg-cli/releases/latest"


def download_archive(
    url: str,
    format: Literal["zip", "tar", "gztar", "bztar", "xztar"],
    extract_dir: os.PathLike[str]
):
    with tempfile.NamedTemporaryFile("wb", delete=False) as file:
        with requests.get(url, stream=True) as r:
            for chunk in r.iter_content(CHUNK_SIZE):
                file.write(chunk)
        file.close()
        shutil.unpack_archive(
            file.name,
            extract_dir=extract_dir,
            format=format  # TODO: make portable
        )
        os.unlink(file.name)


# download own copy of sqlite
# TODO: check dir integrity, not just *empty*
if (
    cfg.external_sqlite is False
    and next(cfg.sqlite_path.parent.iterdir(), None) is None
):
    # TODO: make some logs, progressbars etc
    match platform:
        case "win":
            # TODO: check if x64 sqlite works with x32 python on windows
            ver = "dll-win-x86"
        case "unix":
            ver = "linux-x64"
        case "macos":
            ver = "osx-x64"
        case _:
            raise AssertionError()

    with requests.get(SQLITE_LIST_URL) as r:
        start_i = r.text.find("<!-- Download product data for scripts to read\n")
        start_i = r.text.find("\n", start_i) + 1
        end_i = r.text.find("\n -->\n", start_i)
        buf = io.StringIO(r.text[start_i:end_i])
    for row in csv.DictReader(buf, delimiter=","):
        route = row["RELATIVE-URL"]
        if ver in route:
            break
    else:
        raise AssertionError("no valid version found")

    download_archive(SQLITE_URL + route, "zip", cfg.sqlite_path.parent)

# TODO: check dir integrity, not just *empty*
if (
    isinstance(cfg.external_sqlpkg, bool)
    and next(cfg.sqlpkg_executable.parent.iterdir(), None) is None
):
    match platform:
        case "win":
            platform_ = "windows"
        case "unix":
            platform_ = "linux"
        case "macos":
            platform_ = "darwin"
        case _:
            raise AssertionError()
    machine_ = machine().lower()
    match machine_:
        case "i386":
            machine_ = "386"
        case "amd64" | "arm64":
            ...
        case _:
            raise AssertionError()
    ver = f"{platform_}_{machine_}"

    with requests.get(f"https://api.github.com/repos/{SQLPKG_TARGET}") as r:
        data = json.loads(r.text)
        for asset in data["assets"]:
            if ver in asset["name"]:
                url = asset["browser_download_url"]
                break
        else:
            raise AssertionError()

    download_archive(url, "gztar", cfg.sqlpkg_executable.parent)

# TODO: maybe check for some conflicts?
packages: set[str] = set()
for ep in entry_points(group="sqbucket", name="pkgs"):
    data = ep.load()
    assert isinstance(data, Sequence) and not isinstance(data, str)
    packages.update(str(i).lower() for i in data)
print(packages)
