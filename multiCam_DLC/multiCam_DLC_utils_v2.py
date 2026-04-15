"""
DeepLabCut2.0 Toolbox
https://github.com/AlexEMG/DeepLabCut
A Mathis, alexander.mathis@bethgelab.org
T Nath, nath@rowland.harvard.edu
M Mathis, mackenzie@post.harvard.edu

Boilerplate project creation inspired from DeepLabChop
by Ronny Eichler
"""
import os #, socket
from pathlib import Path
import cv2
import numpy as np
import pandas as pd
import os.path
import yaml
import ruamel.yaml
from multiprocessing import Process
import glob
from pathlib import PurePath
import sys, linecache
import shutil
from utils.file_utils import CONFIG_FILE_PATH
from utils.constants import RAW_DATA_DIR, COMPRESSED_VIDEO_DIR
from utils.logger import get_logger
logger = get_logger("./multiCam_DLC/multiCam_DLC_utils_v2") 


class moveVids(Process):
    def __init__(self):
        super().__init__()
        
    def run(self):
        try:
            dirlist = list()
            destlist = list()
            user_cfg = read_config()
            read_dir = RAW_DATA_DIR
            write_dir = COMPRESSED_VIDEO_DIR
            prev_date_list = [name for name in os.listdir(read_dir)]
            for f in prev_date_list:
                unit_dirR = os.path.join(read_dir, f, user_cfg['unitRef'])
                unit_dirW = os.path.join(write_dir, f, user_cfg['unitRef'])
                if os.path.exists(unit_dirR):
                    prev_expt_list = [name for name in os.listdir(unit_dirR)]
                    for s in prev_expt_list:
                        dirlist.append(os.path.join(unit_dirR, s))
                        destlist.append(os.path.join(unit_dirW, s))
                            
            logger.debug(read_dir)
            logger.debug(write_dir)
            for ndx, s in enumerate(dirlist):
                avi_list = os.path.join(s, '*.avi')
                vid_list = glob.glob(avi_list)
                if not os.path.exists(destlist[ndx]):
                    os.makedirs(destlist[ndx])
                if len(vid_list):
                    for v in vid_list:
                        vid_name = PurePath(v)
                        dest_path = os.path.join(destlist[ndx], vid_name.stem+'.avi')
                        passtest = self.testVids(v,str(dest_path))
                        if not passtest:
                            shutil.copyfile(v,dest_path)
                            
                    passvals = list()
                    for v in vid_list:
                        vid_name = PurePath(v)
                        dest_path = os.path.join(destlist[ndx], vid_name.stem+'.avi')
                        passval = self.testVids(v,str(dest_path))
                        passvals.append(passval)
                        logger.debug(f"passval {passval}")
                        if passval:
                            os.remove(v)
                            logger.info('Successfully transferred %s' % vid_name.stem)
                        else:
                            logger.info('Error transferring %s' % vid_name.stem)
                metafiles = glob.glob(os.path.join(s,'*'))
                for m in metafiles:
                    mname = PurePath(m).name
                    mdest = os.path.join(destlist[ndx],mname)
                    if not os.path.isfile(mdest):
                        shutil.copyfile(m,mdest)
        except:
            exc_type, exc_obj, tb = sys.exc_info()
            f = tb.tb_frame
            lineno = tb.tb_lineno
            filename = f.f_code.co_filename
            linecache.checkcache(filename)
            line = linecache.getline(filename, lineno, f.f_globals)
            logger.exception('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))
                
    def testVids(self, v, dest_path):
        try:
            vid = cv2.VideoCapture(v)
            numberFramesA = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
            vid = cv2.VideoCapture(str(dest_path))
            numberFramesB = int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
            if numberFramesA == numberFramesB and numberFramesA > 0:
                passval = True
            else:
                passval = False
        except:
            passval = False
            exc_type, exc_obj, tb = sys.exc_info()
            f = tb.tb_frame
            lineno = tb.tb_lineno
            filename = f.f_code.co_filename
            linecache.checkcache(filename)
            line = linecache.getline(filename, lineno, f.f_globals)
            logger.exception('EXCEPTION IN ({}, LINE {} "{}"): {}'.format(filename, lineno, line.strip(), exc_obj))
            
        return passval




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
