import logging
import os
from pathlib import Path

import rcp_task_acquisition
from rcp_task_acquisition.utils.logging import get_verbose_logger
from rcp_task_acquisition.utils.trial import get_new_log_file


def _get_logger(name: str = "cart", *, log_filename=None) -> logging.Logger:
    # NB: old implementation, see new utils.logging.get_verbose_logger
    # keeping for now as ref.
    """
    Get a logger with both file and console output.

    Args:
        name (str): Logger name (recommended: module name)

    Returns:
        logging.Logger: Configured logger instance
    """
    # log_dir = Path(RAW_DATA_DIR+ "/logs") #Path("/home/rcp/task-acquisition/logs")
    if log_filename is None:
        log_filename = get_new_log_file()

    if not os.path.exists(log_filename):
        open(log_filename, "w").close()

    # Create logger
    logger = logging.getLogger(name)
    logger.setLevel(logging.DEBUG)  # Record all levels by default

    # Avoid adding duplicate handlers
    if not logger.handlers:
        # File handler (write to file)
        file_handler = logging.FileHandler(log_filename, encoding="utf-8")
        file_handler.setLevel(logging.DEBUG)

        # Console handler (output to terminal)
        console_handler = logging.StreamHandler()
        console_handler.setLevel(logging.INFO)

        # Formatter
        formatter = logging.Formatter(
            fmt="%(asctime)s | %(levelname)s | %(name)s | %(message)s", datefmt="%H:%M:%S"
        )
        file_handler.setFormatter(formatter)
        console_handler.setFormatter(formatter)

        # Add handlers
        logger.addHandler(file_handler)
        logger.addHandler(console_handler)

    return logger


def get_logger(name_path: str):
    rep = name_path.split(".")
    if rep[0] == "rcp_task_acquisition":
        rep[0] = "rcp"
    else:
        rep = ["rcp"] + rep
    return get_verbose_logger(".".join(rep))
