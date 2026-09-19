import logging.config
from multiprocessing import Process

from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.logging import (
    make_log_dict_config,
    setup_logging,
    install_log_exception_hook,
)


logger = get_logger(__name__)


def void_run_no_target(self):
    pass


class ProcessWithLogging(Process):
    @classmethod
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls._orig_run = cls.run
        if cls.run == Process.run:
            # ensure no loop
            cls._orig_run = void_run_no_target
        else:
            del cls.run

    def __init__(self, *args, target=None, **kwargs) -> None:
        self._orig_target = target
        self._orig_args = kwargs.pop("args", None)
        self._orig_kwargs = kwargs.pop("kwargs", None)
        super().__init__(*args, **kwargs, target=self.pre_run)
        self._logging_config = make_log_dict_config()

    def pre_run(self):
        log_dict_config = self._logging_config
        if log_dict_config is None:
            setup_logging()
        else:
            logging.config.dictConfig(log_dict_config)
            install_log_exception_hook()
        target = self._orig_target
        if target is None:
            target = self._orig_run
            args = ()
            kwargs = None
            self._args = self._orig_args
            self._kwargs = self._orig_kwargs
        else:
            args = self._orig_args or ()  # noqa
            kwargs = self._orig_kwargs
        # logger.info("target: %s", target)
        # logger.debug("args=%s, kwargs=%s")
        logger.notice("%s: starting target=%s args=%s kwargs=%s", self.name, target, args, kwargs)
        try:
            target(*args, **(kwargs or {}))  # noqa
        except BaseException as err:
            logger.exception("exiting due to: %s", err)
            raise
