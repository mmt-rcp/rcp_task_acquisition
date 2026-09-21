import multiprocessing
import os
import platform
import shlex
import sys

import matplotlib
import wx

from rcp_task_acquisition.utils.constants import get_rcp_config

# set up matplotlib to be compatible on commandline/spyder
matplotlib.use("qtagg")

from rcp_task_acquisition.utils import logging, trial
from rcp_task_acquisition.panels.SwitchPanel import SwitchPanel


def run_app():

    cfg = get_rcp_config()

    console_start_log_level = os.getenv("RCP_CONSOLE_LOG_LEVEL", "INFO")
    logging.setup_logging(
        multiprocess_enabled=True,
        date_format=logging.DateTimeFormats.hour_time_precise,
        time_precision=3,
        console_handler_level=console_start_log_level,
    )

    unit_serial = cfg.get("unitRef")
    log_file_path = trial.get_new_log_file(unit_serial=unit_serial)
    log_q_listener = logging.get_log_queue_listener()
    if log_q_listener is not None:
        log_q_listener.add_file_handler(
            log_file_path,
            formatter=logging.PreciseTimeFormatter(
                logging.MULTIPROC_LOG_FORMAT,
                datefmt=logging.DateTimeFormats.hour_time_precise,
                time_precision=3,
            ),
        )

    logger = logging.get_verbose_logger("rcp")
    logger.notice("Starting application..")

    # todo
    # logger.notice("Activated app_model with version %s", app_version)
    logger.debug("start cmdline=%s", shlex.join(sys.argv))
    logger.debug("start env:\n%s", "\n".join(f"{k}={v!r}" for k, v in os.environ.items()))

    rc = -1
    try:
        app = wx.App()
        SwitchPanel()  # todo move within App
        logger.info("Running main loop..")
        rc = app.MainLoop()
        logger.verbose("app main loop returned %s", rc)
        return rc
    except KeyboardInterrupt:
        logger.notice("interrupted by user / keyboard interrupt from:", exc_info=True)
    except SystemExit:
        logger.notice("interrupted by system exit from:", exc_info=True)
    except BaseException as err:
        logger.exception("Fatal error: %s", err)
        rc = 1
    finally:
        (logger.success if rc == 0 else logger.error)("exiting application with exitcode=%s", rc)
        logger.debug("closing log manager..")
        try:
            logging.stop_multiproc_logging()
        finally:
            try:
                multiprocessing.get_context().Manager().shutdown()
            except:  # noqa
                pass
    return rc


if __name__ == "__main__":
    run_app()
