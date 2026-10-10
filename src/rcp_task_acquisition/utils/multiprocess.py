import functools
import logging.config
import multiprocessing.queues as mp_queues
import os
import queue
from multiprocessing import Process
from typing import Callable

from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.logging import (
    install_log_exception_hook,
    make_log_dict_config,
    setup_logging,
)

logger = get_logger(__name__)


def void_run_no_target(self):
    logger.warning("%s did not declared a target or custom run", self.__class__)


def relay_to_proc(func: Callable):
    """With ProcessWithRemoteFunction, this allows to call `proc.meth(...)` on the parent process,
    or eventually on any other process, and have the call relayed to the actual related process (`proc`) itself"""

    @functools.wraps(func)
    def wrapped(self: "ProcessWithRemoteFunction", *args, **kwargs):
        if os.getpid() == self.pid:
            func(*args, **kwargs)
        else:
            self._queue.put((func.__name__, args, kwargs))

    return wrapped


class ProcessWithRemoteFunction(Process):
    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self._queue: mp_queues.Queue[None | tuple[str, tuple, dict]] = mp_queues.Queue(maxsize=64)

    def stop(self, *, join: bool = True):
        self._queue.put(None)
        if join:
            self.join()

    def run(self) -> None:
        cmd_q = self._queue
        while True:
            try:
                raw = cmd_q.get(timeout=1)
            except queue.Empty:
                continue
            if raw is None:
                logger.verbose("received None, exiting")
                break
            cmd, args, kwargs = raw
            func: Callable | None = getattr(self, cmd, None)
            if func is None:
                logger.error("unknown command: %s", cmd)
                continue
            try:
                func(*args, **kwargs)  # type: ignore
            except Exception as err:
                logger.exception("%s failed: %s", cmd, err)


class ProcessWithLogging(Process):
    _orig_run: Callable

    @classmethod
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls._orig_run = cls.run
        if cls.run is Process.run:
            # ensure no loop
            cls._orig_run = void_run_no_target
        else:
            del cls.run

    def __init__(self, *args, target: Callable | None = None, **kwargs) -> None:
        self._orig_target = target
        kwargs["target"] = self.pre_run
        super().__init__(*args, **kwargs)
        self._logging_config = make_log_dict_config()

    def pre_run(self, *args, **kwargs):
        log_dict_config = self._logging_config
        if log_dict_config is None:
            setup_logging()
        else:
            logging.config.dictConfig(log_dict_config)
            install_log_exception_hook()
        target = self._orig_target
        self._args = args
        self._kwargs = kwargs
        if target is None:
            target = self._orig_run
            # def run(self): takes no arg/kwarg, so need:
            args = ()
            kwargs = None
            # before call it.
        # logger.info("target: %s", target)
        # logger.debug("args=%s, kwargs=%s")
        logger.notice(
            "%s: starting target=%s args=%s kwargs=%s", self.name, target, self._args, self._kwargs
        )
        try:
            target(*args) if kwargs is None else target(*args, **kwargs)
        except BaseException as err:
            logger.exception("exiting due to: %s", err)
            raise
