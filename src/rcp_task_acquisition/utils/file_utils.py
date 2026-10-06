import os

import ruamel.yaml

from rcp_task_acquisition.utils.constants import (
    CODE_CONFIG_DIR_PATH,
    SCREEN_CONFIG_FILE_NAME,
)
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


def get_screen_config():
    userDataDir = os.path.realpath(CODE_CONFIG_DIR_PATH)
    configPath = os.path.join(userDataDir, SCREEN_CONFIG_FILE_NAME)
    ruamelFile = ruamel.yaml.YAML()

    screen_config = None
    if os.path.exists(configPath):
        with open(configPath, "r") as f:
            screen_config = ruamelFile.load(f)
    if screen_config is None:
        return
    return screen_config


def write_metadata(data, file_path):
    with open(file_path, "w") as metadata_file:
        ruamelFile = ruamel.yaml.YAML()
        ruamelFile.dump(data, metadata_file)


def cam_config_template():
    """
    Creates a template for config.yaml file. This specific order is preserved while saving as yaml file.
    """
    yaml_str = """\
# Camera reference (enter serial numbers for each)
    frontCam:
    sideCam:
    topCam:
    masterCam:
    \n
# Camera settings
    frontCrop:
    sideCrop:
    topCrop:
    exposure:
    framerate:
    bin:
    \n
# User information
    unitRef:
    raw_data_dir:
    COM:
    default_video_dir:
    \n
    
    """
    ruamelFile = ruamel.yaml.YAML()
    cfg_file = ruamelFile.load(yaml_str)
    return cfg_file, ruamelFile


def metadata_template():
    """
    Creates a template for config.yaml file. This specific order is preserved while saving as yaml file.
    """
    yaml_str = """\
# Version
    version:
    \n
    
# Cameras
    cameras:
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

# Labjack Settings
    actual_scan_rate:
    hardware:
    \n

# Task
    task:
    task_settings:
    trial_data:
    task_notes:
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
