from rcp_task_acquisition.utils import win_os
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


def set_high_prio(
    *,
    win32api=win_os.win32api,
    win32process=win_os.win32process,
    win32con=win_os.win32con,  # noqa
):
    if win32api is None:
        pass  # todo
    else:
        pid = win32api.GetCurrentProcessId()
        handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
        try:
            win32process.SetPriorityClass(-1, win32process.HIGH_PRIORITY_CLASS)
        except Exception as err:
            logger.warning("Could not set current process to high prio: %s", err)
        else:
            logger.info("Successfully set current process to high prio")
