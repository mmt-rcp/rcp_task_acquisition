#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Created on Fri Aug  9 09:21:35 2019

@author: bioelectrics
"""
import subprocess
from multiprocessing import Process
import glob
import os
from pathlib import PurePath
import cv2
import rcp_task_acquisition.multiCam_DLC.multiCam_DLC_utils_v2 as clara
import shutil
from datetime import datetime, timedelta, date
from rcp_task_acquisition.utils.constants import RAW_DATA_DIR, COMPRESSED_VIDEO_DIR
# from utils.logging import logger
from rcp_task_acquisition.utils.logger import get_logger
logger = get_logger("./multiCam_DLC/compressVideos_v3") 

maximumRecordingHistory = 2000

class CLARA_compress(Process):
    def __init__(self):
        super().__init__()
        
    def run(self):
        try:
            dirlist = list()
            destlist = list()
            user_cfg = clara.read_config()
            read_dir = RAW_DATA_DIR
            write_dir = COMPRESSED_VIDEO_DIR
            prev_date_list = [name for name in os.listdir(read_dir)]
            for f in prev_date_list:
                
                # Check if date is beyond threshold
                year = int(f[:4])
                month = int(f[4:6])
                day = int(f[6:])
                if (datetime.today().date() - date(year, month, day)).days > maximumRecordingHistory: 
                    continue
                
                unit_dirR = os.path.join(read_dir, f, user_cfg['unitRef'])
                unit_dirW = os.path.join(write_dir, f, user_cfg['unitRef'])
                if os.path.exists(unit_dirR):
                    prev_expt_list = [name for name in os.listdir(unit_dirR)]
                    for s in prev_expt_list:
                        dirlist.append(os.path.join(unit_dirR, s))
                        destlist.append(os.path.join(unit_dirW, s))
                            
            
            for ndx, s in enumerate(dirlist):
                avi_list = os.path.join(s, '*.avi')
                vid_list = glob.glob(avi_list)
                if not os.path.exists(destlist[ndx]):
                    os.makedirs(destlist[ndx])
                if len(vid_list):
                    filenames = list()
                    for v in vid_list:
                        vid_name = PurePath(v)
                        dest_path = os.path.join(destlist[ndx], vid_name.stem+'.mp4')
                        passtest = self.testVids(v,str(dest_path))
                        if passtest == False:
                            # command = 'ffmpeg -y -i ' + v + ' -c:v libx264 -preset veryfast -strict experimental -crf 17 -loglevel quiet ' + str(dest_path)
                            # command = 'ffmpeg -y -i ' + v + ' -map 0:v:0 -fps_mode passthrough -vsync 0 -c:v libx265 -preset veryfast -crf 17 -loglevel quiet ' + str(dest_path)
                            command = 'ffmpeg -y -i ' + v + ' -fps_mode passthrough -c:v libx265 -preset veryfast -crf 17 -loglevel quiet ' + str(dest_path)
                            # print(command)
                            proc = subprocess.Popen([command, '/usr/bin'], shell=True, stdout=subprocess.PIPE)
                            filenames.append(vid_name)
                            proc.wait()
                            proc.kill()
                        
                        passval = self.testVids(v,str(dest_path))
                        if passval:
                            os.remove(v)
                            
                            logger.info('Successfully compressed %s' % vid_name.stem)
                            # logger.info('Successfully compressed %s' % vid_name.stem)
                        else:
                            
                            logger.error('Error compressing %s' % vid_name.stem)
                            # logger.info('Error compressing %s' % vid_name.stem)
                metafiles = glob.glob(os.path.join(s,'*'))
                for m in metafiles:
                    mname = PurePath(m).name
                    mdest = os.path.join(destlist[ndx],mname)
                    if not os.path.isfile(mdest) or (os.path.getsize(m) != os.path.getsize(mdest)): #: # or not (old_file_size == new_size)
                        shutil.copyfile(m,mdest)
            # logger.info('Compression complete!!!')
            logger.info("compression complete")
        except Exception as ex:
            logger.exception(ex)
    
      
    
    def testVids(self, v, dest_path):
        try:
            # vid = cv2.VideoCapture(v)
            numberFramesA = self.count_frames_ffprobe(v) #int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
            # print(f"{os.path.split(v)[1]}: {numberFramesA}")
            # vid = cv2.VideoCapture(str(dest_path))
            numberFramesB = self.count_frames_ffprobe(dest_path) #int(vid.get(cv2.CAP_PROP_FRAME_COUNT))
            # print(f"{os.path.split(dest_path)[1]}: {numberFramesB}")
            if numberFramesA == numberFramesB and numberFramesA > 1 and numberFramesB > 1:
                passval = True
            else:
                passval = False
        except:
            passval = False
            
        return passval
    
    def count_frames_ffprobe(self, path):
        cmd = [
            "ffprobe",
            "-v", "error",
            "-select_streams", "v:0",
            "-count_frames",
            "-show_entries", "stream=nb_read_frames",
            "-of", "default=nokey=1:noprint_wrappers=1",
            path
        ]
        return int(subprocess.check_output(cmd).decode().strip())
 
# n_raw = count_frames_ffprobe(orig_path)
# n_comp = count_frames_ffprobe(dest_path)
 
# print(n_raw, n_comp, n_comp == n_raw)  


