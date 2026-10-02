import datetime
import platform
from pathlib import Path

from rcp_task_acquisition.utils.constants import RAW_DATA_DIR


def _make_front_part(date_string: str, unit_serial: str, file_count: int | str) -> str:
    return "_".join((date_string, unit_serial, f"{file_count}"))


def _make_log_file_name(front: str) -> str:
    return f"{front}.log"


def get_new_log_file(
    *,
    base_dir: Path = RAW_DATA_DIR,
    dt_now: None | datetime.datetime = None,
    unit_serial: None | str = None,
) -> Path:
    if dt_now is None:
        dt_now = datetime.datetime.now()
    if unit_serial is None:
        unit_serial = platform.node()
    date_string = dt_now.strftime("%Y%m%d")
    right_path = Path(date_string, unit_serial)
    log_dir = base_dir.joinpath(right_path)
    # Ensure the log directory exists
    log_dir.mkdir(parents=True, exist_ok=True)
    search_pat = _make_log_file_name(_make_front_part(date_string, unit_serial, "*"))
    prev_files = list(log_dir.glob(search_pat))
    idx = 1 + len(prev_files)
    log_file = log_dir.joinpath(
        _make_log_file_name(_make_front_part(date_string, unit_serial, f"{idx:03d}"))
    )
    return log_file
