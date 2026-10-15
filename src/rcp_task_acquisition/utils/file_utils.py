import os
from pathlib import Path
from typing import Any

import ruamel.yaml

from rcp_task_acquisition.utils import config
from rcp_task_acquisition.utils.constants import (
    CODE_CONFIG_DIR_PATH,
    SCREEN_CONFIG_FILE_NAME,
)
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


def write_metadata(data: dict[str, Any], file_path: str | Path) -> None:
    file_path = Path(file_path)
    logger.info("writing metadata to %s", file_path)
    with file_path.open("w") as fh:
        dumper = ruamel.yaml.YAML()
        dumper.dump(data, fh)


def metadata_template() -> ruamel.yaml.CommentedMap:
    """
    Creates a template for config.yaml file. This specific order is preserved while saving as yaml file.
    """
    yaml_str = """\
# Version
    version:
    \n
    
# Experiment
    Designer:
    administrator_id:
    Task:
    StartTime_Local:
    StartTime_UTC:
    EndTime_Local:
    EndTime_UTC:
    Collection:
    duration (s):
    unitRef:
    \n

# Participant
    participant_id:
    participant_details:
    \n

# Screen Config
    screen_settings:
    \n

# Task
    task:
    task_settings:
    trial_data:
    task_notes:
    \n

# Cameras
    cameras:
    \n

# Labjack Settings
    actual_scan_rate:
    hardware:
    \n
"""

    ruamelFile = ruamel.yaml.YAML()
    meta_cfg = ruamelFile.load(yaml_str)
    return meta_cfg


def read_metadata(path: Path):
    loader = ruamel.yaml.YAML()
    with path.open("r") as f:
        cfg = loader.load(f)
    return cfg
