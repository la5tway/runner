import logging
from pathlib import Path
from time import sleep
from typing import Callable

from .base import Reloader
from .subprocess_mixin import get_subprocess


class TriggerReloader(Reloader):
    def __init__(
        self,
        should_restart: Path | None,
        target: Callable[[], None] | None = None,
        name: str | None = None,
        reload_delay: float = 0.25,
        logger: logging.Logger | None = None,
    ) -> None:
        super().__init__(
            target=target,
            name=name,
            reload_delay=reload_delay,
            logger=logger,
        )
        if not should_restart:
            should_restart = Path(__file__).parent / "sync.txt"
        self.should_restart = should_restart
        self.started: bool = False

    def restart(self) -> None:
        self.should_restart.write_text("1")

    def _startup(self) -> None:
        if self.started:
            return
        self.started = True
        if self.target is None:
            raise RuntimeError("target is required")
        super()._startup()
        self.process = get_subprocess(
            target=self.target,
        )
        self.process.start()

    def _observe(self) -> None:
        while self.started:
            t = self.should_restart.read_text()
            if not t:
                sleep(self.reload_delay)
            else:
                self.logger.warning(f"{self.name} received signal. Reloading...")
                self._restart()

    def _restart(self):
        if self.target is None:
            raise RuntimeError("target is required")
        self.should_restart.write_text("")
        self.mtimes = {}
        self.process.terminate()
        self.process.join()

        self.process = get_subprocess(target=self.target)
        self.process.start()

    def _shutdown(self) -> None:
        self.process.terminate()
        self.process.join()

        self.logger.info(f"Stopping reloader process [{self.pid}]")
