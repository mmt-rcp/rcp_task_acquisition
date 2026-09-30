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
    logger.warning("%s did not declared a target or custom run", self.__class__)


class ProcessWithLogging(Process):
    @classmethod
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        cls._orig_run = cls.run
        if cls.run is Process.run:
            # ensure no loop
            cls._orig_run = void_run_no_target
        else:
            del cls.run

    def __init__(self, *args, target=None, **kwargs) -> None:
        self._orig_target = target
        super().__init__(
            *args,
            **kwargs,
            target=self.pre_run,
        )
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
            target(*args) if kwargs is None else target(*args, **kwargs)  # noqa
        except BaseException as err:
            logger.exception("exiting due to: %s", err)
            raise
