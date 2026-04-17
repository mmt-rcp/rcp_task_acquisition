"""
DeepLabCut2.0 Toolbox
https://github.com/AlexEMG/DeepLabCut
A Mathis, alexander.mathis@bethgelab.org
T Nath, nath@rowland.harvard.edu
M Mathis, mackenzie@post.harvard.edu

Boilerplate project creation inspired from DeepLabChop
by Ronny Eichler
"""
import os
from pathlib import Path
import os.path
import yaml
import ruamel.yaml
from rcp_task_acquisition.utils.file_utils import CONFIG_FILE_PATH
from rcp_task_acquisition.utils.logger import get_logger
logger = get_logger("./multiCam_DLC/multiCam_DLC_utils_v2") 






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

def read_config():
    """
    Reads structured config file

    """
    # usrdatadir = os.path.dirname(CONFIG_FILE_PATH)
    configname = os.path.join(CONFIG_FILE_PATH, 'userdata.yaml')
    ruamelFile = ruamel.yaml.YAML(typ="safe")
    path = Path(configname)
    if os.path.exists(path):
        try:
            with open(path, 'r') as f:
                cfg = ruamelFile.load(f)
        except Exception as err:
            if err.args[2] == "could not determine a constructor for the tag '!!python/tuple'":
                with open(path, 'r') as ymlfile:
                  cfg = yaml.load(ymlfile,Loader=yaml.SafeLoader)
                  write_config(cfg)
    else:
        cfg = 'none'
        
    return(cfg)

def write_config(cfg):
    """
    Write structured config file.
    """
    # usrdatadir = os.path.dirname(CONFIG_FILE_PATH)
    configname = os.path.join(CONFIG_FILE_PATH, 'userdata.yaml')
    with open(configname, 'w') as cf:
        ruamelFile = ruamel.yaml.YAML()
        ruamelFile.dump(cfg, cf)
        

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
    StartTime:
    EndTime:
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
        with open(path, 'r') as f:
            cfg = ruamelFile.load(f)
    return(cfg)

def write_metadata(cfg, path):
    with open(path, 'w') as cf:
        ruamelFile = ruamel.yaml.YAML()
        for key in cfg.keys():
            cfg[key]=cfg[key]
        ruamelFile.dump(cfg, cf)
