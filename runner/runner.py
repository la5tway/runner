import logging
import signal
import threading
from asyncio import Event, create_task, get_event_loop, iscoroutine
from asyncio import sleep as asleep
from logging import Logger
from types import FrameType
from typing import Any, Awaitable, Callable

from .common import Container, RunnerEventHandler


class Runner:
    def __init__(
        self,
        container: Container,
        logger: logging.Logger | None = None,
        before_start: list[RunnerEventHandler] | None = None,
        on_start: list[RunnerEventHandler] | None = None,
        after_start: list[RunnerEventHandler] | None = None,
        on_stop: list[RunnerEventHandler] | None = None,
        log_config: Callable[[], None] | None = None,
        callback_notify: Callable[..., Awaitable[None]] | None = None,
        timeout_notify: float = 30.0,
    ) -> None:
        if log_config:
            log_config()

        self.container = container
        container.add_instance(self)

        self.should_exit = Event()

        self.callback_notify = callback_notify
        self.timeout_notify = timeout_notify
        self.last_notified = 0.0
        self._notify_task = None

        self.before_start = BeforeStartContainer(self)
        if before_start:
            for handler in before_start:
                self.before_start.append(handler)
        self.on_start = CallableContainer(self)
        if on_start:
            for handler in on_start:
                self.on_start.append(handler)
        self.after_start = CallableContainer(self)
        if after_start:
            for handler in after_start:
                self.after_start.append(handler)
        self.on_stop = CallableContainer(self)
        if on_stop:
            for handler in on_stop:
                self.on_stop.append(handler)
        if not logger:
            self.logger = logging.getLogger(self.__class__.__name__)
        else:
            self.logger = logger.getChild(self.__class__.__name__)
            container.add_instance(logger, Logger)
        self.started = False

    async def start(self):
        await self._actual_start()

    async def stop(self):
        await self._actual_stop()

    async def _notify(self):
        assert self.callback_notify
        while True:
            await self.callback_notify()
            await asleep(self.timeout_notify)

    async def main_loop(self) -> None:
        await self.should_exit.wait()

    async def _actual_start(self):
        if self.started:
            return
        self.started = True

        self._install_signal_handlers()
        self.logger.info("Starting...")
        if self.callback_notify:
            self._notify_task = create_task(self._notify())
        if self.before_start:
            await self.before_start.fire()

        self.provider = self.container.build_provider()

        if self.on_start:
            await self.on_start.fire()

        if self.after_start:
            await self.after_start.fire()

        self.logger.info("Started")

        await self.main_loop()
        await self.stop()

    async def _actual_stop(self):
        self.logger.info("Stopping...")
        if self._notify_task:
            self._notify_task.cancel()
        await self.on_stop.fire()
        self.started = False
        self.logger.info("Stopped")

    def _on_start(self):
        self.provider = self.container.build_provider()

    HANDLED_SIGNALS = (
        signal.SIGINT,  # Unix signal 2. Sent by Ctrl+C.
        signal.SIGTERM,  # Unix signal 15. Sent by `kill <pid>`.
    )

    def _handle_exit(self, sig: int, frame: FrameType | None) -> None:
        self.should_exit.set()

    def _install_signal_handlers(self) -> None:
        if threading.current_thread() is not threading.main_thread():
            return

        loop = get_event_loop()

        try:
            for sig in self.HANDLED_SIGNALS:
                loop.add_signal_handler(
                    sig,
                    self._handle_exit,
                    sig,
                    None,
                )
        except NotImplementedError:  # pragma: no cover
            # Windows
            for sig in self.HANDLED_SIGNALS:
                signal.signal(sig, self._handle_exit)


class CallableContainerMixin:
    _handlers: list[RunnerEventHandler]

    def append(self, handler: RunnerEventHandler) -> None:
        self._handlers.append(handler)

    def __len__(self) -> int:
        return len(self._handlers)

    def __call__(self, handler: RunnerEventHandler | None) -> Any:
        if handler:
            self.append(handler)
            return handler

        def decorator(fn: RunnerEventHandler):
            self.append(fn)
            return fn

        return decorator


class BeforeStartContainer(CallableContainerMixin):
    def __init__(self, runner: Runner) -> None:
        self.runner = runner
        self._handlers: list[RunnerEventHandler] = []

    async def fire(self) -> None:
        for handler in self._handlers:
            self.runner.logger.debug(f"call handler {handler}")
            coro = handler(self.runner)
            if iscoroutine(coro):
                await coro


class CallableContainer(BeforeStartContainer):
    def __init__(self, runner: Runner) -> None:
        super().__init__(runner)

    async def fire(self) -> None:
        for handler in self._handlers:
            self.runner.logger.debug(f"call handler {handler}")
            coro = handler(**self.runner.provider.resolve_params(handler))
            if iscoroutine(coro):
                await coro
