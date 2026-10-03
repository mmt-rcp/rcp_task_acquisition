import logging
import os
from pathlib import Path

import rcp_task_acquisition
from rcp_task_acquisition.utils.logging import get_verbose_logger
from rcp_task_acquisition.utils.trial import get_new_log_file


def get_logger(name_path: str):
    rep = name_path.split(".")
    if rep[0] == "rcp_task_acquisition":
        rep[0] = "rcp"
    else:
        rep = ["rcp"] + rep
    return get_verbose_logger(".".join(rep))
