import logging
import os
from pathlib import Path
from typing import Callable, Iterator

from .base import Reloader
from .subprocess_mixin import get_subprocess


class FileReloader(Reloader):
    def __init__(
        self,
        target: Callable[[], None] | None = None,
        name: str | None = None,
        reload_delay: float = 0.25,
        reload_dirs: list[str] | str | None = None,
        reload_includes: list[str] | str | None = None,
        reload_excludes: list[str] | str | None = None,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(
            name=name,
            target=target,
            reload_delay=reload_delay,
            logger=logger,
        )
        self.reload_dirs_raw = reload_dirs
        self.reload_includes_raw = reload_includes
        self.reload_excludes_raw = reload_excludes

        self.should_restart: bool = False

        self.mtimes: dict[Path, float] = {}
        self.reload_dirs: list[Path]
        self.reload_includes: list[str]
        self.reload_excludes: list[str]

    def restart(self) -> None:
        self.should_restart = True

    def __iter__(self) -> Iterator[list[Path] | None]:
        return self

    def __next__(self) -> list[Path] | None:
        return self._should_restart()

    def _startup(self) -> None:
        if self.target is None:
            raise RuntimeError("target is required")
        super()._startup()
        self._init_reload_dirs()
        self.process = get_subprocess(
            target=self.target,
        )
        self.process.start()

    def _observe(self) -> None:
        for changes in self:
            if changes:
                self.logger.warning(
                    f"{self.name} detected changes in "
                    f"{', '.join(map(self._display_path, changes))}. Reloading...",
                )
                self._restart()
            elif self.should_restart:
                self.logger.warning(
                    f"{self.name} detected restart trigger. Reloading..."
                )
                self._restart()

    def _restart(self):
        if self.target is None:
            raise RuntimeError("target is required")
        self.should_restart = False
        self.mtimes = {}
        self.process.terminate()
        self.process.join()

        self.process = get_subprocess(target=self.target)
        self.process.start()

    def _shutdown(self) -> None:
        self.process.terminate()
        self.process.join()

        self.logger.info(f"Stopping reloader process [{self.pid}]")

    def _should_restart(self) -> list[Path] | None:
        self._pause()

        for file in self._iter_py_files():
            try:
                mtime = file.stat().st_mtime
            except OSError:  # pragma: nocover
                continue

            old_time = self.mtimes.get(file)
            if old_time is None:
                self.mtimes[file] = mtime
                continue
            elif mtime > old_time:
                return [file]
        return None

    def _pause(self) -> None:
        if self.should_exit.wait(self.reload_delay):
            raise StopIteration()

    def _iter_py_files(self) -> Iterator[Path]:
        for reload_dir in self.reload_dirs:
            for path in list(reload_dir.rglob("*.py")):
                yield path.resolve()

    def _init_reload_dirs(self):
        reload_dirs = self._normalize_dirs(self.reload_dirs_raw)

        self.reload_includes, self.reload_dirs = self._resolve_reload_patterns(
            self._normalize_dirs(self.reload_includes_raw),
            reload_dirs,
        )

        self.reload_excludes, self.reload_dirs_excludes = self._resolve_reload_patterns(
            self._normalize_dirs(self.reload_excludes_raw), []
        )

        reload_dirs_tmp = self.reload_dirs.copy()

        for directory in self.reload_dirs_excludes:
            for reload_directory in reload_dirs_tmp:
                if (
                    directory == reload_directory
                    or directory in reload_directory.parents
                ):
                    try:
                        self.reload_dirs.remove(reload_directory)
                    except ValueError:
                        pass

        for pattern in self.reload_excludes:
            if pattern in self.reload_includes:
                self.reload_includes.remove(pattern)

        if not self.reload_dirs:
            if reload_dirs:
                self.logger.warning(
                    f"Provided reload directories {reload_dirs} did not contain valid "
                    + "directories, watching current working directory."
                )
            self.reload_dirs = [Path(os.getcwd())]

        self.logger.info(
            "Will watch for changes in these directories: "
            f"{sorted(list(map(str, self.reload_dirs)))}",
        )

    def _normalize_dirs(
        self,
        dirs: list[str] | str | None,
    ) -> list[str]:
        if dirs is None:
            return []
        if isinstance(dirs, str):
            return [dirs]
        return list(set(dirs))

    def _resolve_reload_patterns(
        self,
        patterns_list: list[str],
        directories_list: list[str],
    ) -> tuple[list[str], list[Path]]:

        directories: list[Path] = list(set(map(Path, directories_list.copy())))
        patterns: list[str] = patterns_list.copy()

        current_working_directory = Path.cwd()
        for pattern in patterns_list:
            # Special case for the .* pattern, otherwise this would only match
            # hidden directories which is probably undesired
            if pattern == ".*":
                continue
            patterns.append(pattern)
            if self._is_dir(Path(pattern)):
                directories.append(Path(pattern))
            else:
                for match in current_working_directory.glob(pattern):
                    if self._is_dir(match):
                        directories.append(match)

        directories = list(set(directories))
        directories = list(map(Path, directories))
        directories = list(map(lambda x: x.resolve(), directories))
        directories = list(
            set(
                [
                    reload_path
                    for reload_path in directories
                    if self._is_dir(reload_path)
                ]
            )
        )

        children = []
        for j in range(len(directories)):
            for k in range(j + 1, len(directories)):
                if directories[j] in directories[k].parents:
                    children.append(directories[k])  # pragma: py-darwin
                elif directories[k] in directories[j].parents:
                    children.append(directories[j])

        directories = list(set(directories).difference(set(children)))

        return list(set(patterns)), directories

    def _is_dir(self, path: Path) -> bool:
        try:
            if not path.is_absolute():
                path = path.resolve()
            return path.is_dir()
        except OSError:
            return False

    def _display_path(self, path: Path) -> str:
        try:
            return f"'{path.relative_to(Path.cwd())}'"
        except ValueError:
            return f"'{path}'"
