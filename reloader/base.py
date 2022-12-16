import logging
import os
import signal
import threading
from types import FrameType
from typing import Callable


class Reloader:
    HANDLED_SIGNALS = (
        signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
        signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
    )

    def __init__(
        self,
        target: Callable[[], None] | None = None,
        name: str | None = None,
        reload_delay: float = 0.25,
        logger: logging.Logger | None = None,
    ) -> None:
        if not name:
            name = self.__class__.__name__
        self.name = name
        self.target = target
        self.reload_delay = reload_delay
        self.should_exit = threading.Event()
        self.pid = os.getpid()
        if not logger:
            self.logger = logging.getLogger(name)
        else:
            self.logger = logger.getChild(name)

    def start(self) -> None:
        self._startup()
        self._observe()
        self._shutdown()

    def stop(
        self,
        sig: int | None = None,
        frame: FrameType | None = None,
    ) -> None:
        self.should_exit.set()

    def restart(self) -> None:
        ...

    def _startup(self) -> None:
        self.logger.info(f"Started reloader process [{self.pid}] using {self.name}")
        self._init_signal_handlers()

    def _observe(self) -> None:
        ...

    def _shutdown(self) -> None:
        ...

    def _signal_handler(
        self,
        sig: int,
        frame: FrameType | None,
    ) -> None:
        self.stop(sig=sig, frame=frame)

    def _init_signal_handlers(self):
        for sig in self.HANDLED_SIGNALS:
            signal.signal(sig, self._signal_handler)
