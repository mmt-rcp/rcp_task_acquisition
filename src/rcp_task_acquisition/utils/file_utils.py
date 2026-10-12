import os
from typing import Any

import ruamel.yaml

from rcp_task_acquisition.utils import config
from rcp_task_acquisition.utils.constants import (
    CODE_CONFIG_DIR_PATH,
    SCREEN_CONFIG_FILE_NAME,
)
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


def write_metadata(data: dict[str, Any], file_path) -> None:
    logger.info("writing metadata to %s", file_path)
    data = config.to_raw_recursive(data)
    with open(file_path, "w") as metadata_file:
        ruamelFile = ruamel.yaml.YAML()
        ruamelFile.dump(data, metadata_file)


def metadata_template():
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

# Task
    task:
    task_settings:
    trial_data:
    task_notes:
    
# Screen Config
    screen_settings:
    \n

# Labjack Settings
    actual_scan_rate:
    hardware:
    \n

# Cameras
    cameras:
    \n
    """

    ruamelFile = ruamel.yaml.YAML()
    cfg_file = ruamelFile.load(yaml_str)
    return cfg_file, ruamelFile


def read_metadata(path):
    ruamelFile = ruamel.yaml.YAML()
    if os.path.exists(path):
        with open(path, "r") as f:
            cfg = ruamelFile.load(f)
    return cfg
