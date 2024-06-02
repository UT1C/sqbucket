from typing import Literal, Annotated
from pathlib import Path
from dataclasses import dataclass, asdict
import json
import sys
import functools
import shutil
import logging
import ctypes.util

cfg: "Config"
meta: "Meta"

logger = logging.getLogger("sqbucket")


@dataclass
class Config:
    external_sqlite: bool | Annotated[str, "Path"] = False
    external_sqlpkg: bool | Annotated[str, "Path"] = True
    external_pkg_storage: bool | Annotated[str, "Path"] = False

    @functools.cached_property
    def sqlite_path(self) -> Path:
        match self.external_sqlite:
            case str():
                path = Path(self.external_sqlite).resolve()
                assert path.exists() and path.is_file(), f"invalid external sqlite: {path}"
                return path
            case True:
                path = ctypes.util.find_library("sqlite3")
                assert path is not None, "no external sqlite found"
                return Path(path)
        path = (meta.storage_path / "lib").resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path / "sqlite3"

    @functools.cached_property
    def sqlpkg_executable(self) -> Path:
        match self.external_sqlpkg:
            case str():
                return Path(self.external_sqlpkg).resolve()
            case True:
                path = shutil.which("sqlpkg")
                if path is not None:
                    return Path(path)
                logger.info("no external sqlpkg found, fallback to internal")

        path = (meta.storage_path / "sqlpkg").resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path / "sqlpkg"

    @functools.cached_property
    def pkg_storage(self) -> Path:
        if self.external_pkg_storage is True:
            path = Path.cwd() / ".sqlpkg"
            if not (path.exists() and path.is_dir()):
                path = Path.home() / ".sqlpkg"
        elif isinstance(self.external_sqlpkg, str):
            path = Path(self.external_sqlpkg).resolve()
            assert path.name == ".sqlpkg", "invalid package storage path"
        elif self.external_pkg_storage is False:
            path = meta.storage_path / ".sqlpkg"

        path = path.resolve()
        path.mkdir(parents=True, exist_ok=True)
        return path


class Meta:
    platform: Literal["win", "unix", "macos"]
    storage_path: Path

    def __init__(self) -> None:
        platform = sys.platform.lower()
        if platform == "win32":
            self.platform = "win"
            self.storage_path = Path.home() / ".sqbucket"
        else:
            if platform == "darwin":
                self.platform = "macos"
            else:
                self.platform = "unix"
            self.storage_path = Path.home() / ".local" / "sqbucket"

        self.validate()

    @functools.cached_property
    def cfg_path(self) -> Path:
        return self.storage_path / "config.json"

    def validate(self):
        self.storage_path.mkdir(parents=True, exist_ok=True)
        self.cfg_path.touch(exist_ok=True)


def init():
    global cfg, meta

    meta = Meta()

    with open(meta.cfg_path, "r") as file:
        try:
            data = json.load(file)
        except json.JSONDecodeError:
            data = None
    if data:
        cfg = Config(**data)
    else:
        cfg = Config()
        with open(meta.cfg_path, "w") as file:
            json.dump(asdict(cfg), file, indent=4)


init()
