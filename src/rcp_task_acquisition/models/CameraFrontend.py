import ctypes
import multiprocessing
import os
import queue
import shutil
import time
from dataclasses import dataclass
from multiprocessing import Array, Queue, Value

import cv2
import numpy as np
import wx
from matplotlib.image import AxesImage

import rcp_task_acquisition.models.CameraProcess as spin
from rcp_task_acquisition.models.CameraProcess import CameraCommand
from rcp_task_acquisition.models.Crop import Crop
from rcp_task_acquisition.models.SerialDevice import SerialDevice
from rcp_task_acquisition.models.Warnings import WarnCat, WarningHandler
from rcp_task_acquisition.panels.GraphPanel import GraphPanel
from rcp_task_acquisition.panels.ImagePanel import ImagePanel
from rcp_task_acquisition.panels.ParticipantMonitorPanel import MonitorPanel
from rcp_task_acquisition.utils import config
from rcp_task_acquisition.utils.constants import CAM_MAX_HEIGHT, CAM_MAX_WIDTH, DOWNSAMPLE_VAL
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.run_context import RcpRunContext
from rcp_task_acquisition.utils.typing import SharedArray, SharedInt

logger = get_logger(__name__)


@dataclass
class FrameDims:
    x1: int
    x2: int
    y1: int
    y2: int
    h: int
    w: int
    dispSize: int


@dataclass
class CamSettings:
    name: str
    serial: str
    is_primary: bool
    size: int
    shape: list[int]
    bin_val: int
    frame_dims: list[int]
    decrease_val: int
    actual_framerate: None | float
    exposure: None | float
    cam_tests: np.ndarray
    contrast_tests: np.ndarray
    frame: np.ndarray
    frameBuff: np.ndarray
    array4feed: SharedArray
    frmGrab: SharedInt
    camq: multiprocessing.Queue
    camq_p2read: multiprocessing.Queue
    frame_size: None | FrameDims


class Camera:
    def __init__(
        self,
        serial: SerialDevice,
        panel: GraphPanel,
        image_panel: ImagePanel,
        contrast_test: wx.ToggleButton,
        focus_test: wx.ToggleButton,
        monitor: MonitorPanel,
        *,
        rcp_context: RcpRunContext,
    ):
        self._rcp_context = rcp_context
        self.serial = serial
        self.shared = Value(ctypes.c_byte, 0)
        self.camaq = Value(ctypes.c_byte, 0)
        self.frmaq = Value(ctypes.c_int, 0)
        self.reset_variables()
        self.dtype = "uint8"
        self.cam_crop = Crop()
        self.ctrl_panel = panel
        self.image_panel = image_panel
        self.contrast_test = contrast_test
        self.focus_test = focus_test
        self.warning = WarningHandler()
        self.trial = 0
        self.session = 0
        self.participant_monitor = monitor
        self.framerate: float = 0
        self.crop = False
        self.cam_dict: dict[str, CamSettings] = {}
        self.multi_cameras: list[spin.multiCam_DLC_Cam] = []
        #
        self.labjack_scan_rate = None
        self.primary_cams: list[str] = []
        self.secondary_cams: list[str] = []
        self.cam_pointer = 0
        self.im: list[AxesImage] = []
        self.x1 = 0
        self.y1 = 0
        self.shared.value = 0
        self.camaq.value = 0
        self.frmaq.value = 0
        self.crop = True
        self.hardware_test = True

    def setup(
        self,
        cams_cfg: config.CamerasDictConfig,
        is_unconnected: bool,
        requested_framerate: float,
    ):
        logger.info("Camera.setup: cams_cfg: %s", cams_cfg)
        self.cam_crop = Crop()
        self.framerate = requested_framerate
        self.reset_variables()
        self.cam_dict.clear()

        for cam_item, cfg in cams_cfg.items():
            name = cam_item.value
            if not cfg.in_use:
                logger.debug("skipping %s not in_use", cam_item)
                continue

            cam_bin = int(cfg.bin)
            cam_dims = [
                0,
                int(CAM_MAX_HEIGHT / DOWNSAMPLE_VAL / cam_bin),
                0,
                int(CAM_MAX_WIDTH / DOWNSAMPLE_VAL / cam_bin),
            ]
            is_primary = bool(cfg.ismaster or is_unconnected)
            new_cam = CamSettings(
                name=name,
                serial=cfg.serial,
                is_primary=is_primary,
                size=cam_dims[1] * cam_dims[3] * 3,
                shape=[cam_dims[1], cam_dims[3], 3],
                bin_val=cam_bin,
                frame_dims=cam_dims,
                decrease_val=int(cfg.framerate_decrease_factor),
                actual_framerate=None,
                exposure=None,
                cam_tests=np.full(shape=30 * 2, fill_value=np.nan),
                contrast_tests=np.full(shape=30 * 2, fill_value=np.nan),
                frame=np.zeros([cam_dims[1], cam_dims[3], 3], dtype="ubyte"),
                frameBuff=np.zeros(cam_dims[1] * cam_dims[3] * 3, dtype="ubyte"),
                array4feed=Array(ctypes.c_ubyte, cam_dims[1] * cam_dims[3] * 3),
                frmGrab=Value(ctypes.c_byte, 0),
                camq=Queue(),
                camq_p2read=Queue(),
                frame_size=None,
            )
            self.cam_dict[new_cam.serial] = new_cam

            self.cam_crop.add_crop(cfg.crop)
            if cfg.ismaster or is_unconnected:
                self.primary_cams.append(new_cam.serial)
            else:
                self.secondary_cams.append(new_cam.serial)

        camCt = len(self.cam_dict)
        cam_names = [cam.name for cam in self.cam_dict.values()]
        self.ctrl_panel.hardware_test(30 * 2, camCt, cam_names)

        self.figure, self.axes, self.canvas = self.image_panel.getfigure()
        for ndx in range(self.cam_pointer, self.cam_pointer + 2):
            serial = list(self.cam_dict)[ndx]
            self.im.append(self.axes[ndx].imshow(self.cam_dict[serial].frame))
            self.im[ndx].set_clim(0, 255)
            self.cam_crop.update_crop(ndx, self.axes[ndx], self.cam_dict[serial].frame_dims)
        self.image_panel.update_names(
            [
                self.cam_dict[list(self.cam_dict)[self.cam_pointer]].name,
                self.cam_dict[list(self.cam_dict)[self.cam_pointer + 1]].name,
            ]
        )
        self.image_panel.draw()

    def initialize(self, event):
        self.serial.init_serial()
        self.initThreads()
        try:
            self.updateSettings(event)
        except Exception as err:
            logger.exception("Error updating settings: %s", err)
            logger.info("Trying to fix cameras. Please wait...")
            self.deinitThreads()
            self.camReset(event)
            self.initThreads()

            try:
                self.updateSettings(event)
            except Exception as err:
                logger.exception("Error reupdating settings: %s", err)
                return False
        self.get_exposure(event)
        self.updateSettings(event)
        self.camaq.value = 1
        self.startAq()
        time.sleep(0.5)
        self.camaq.value = 0
        self.stopAq()

        for ndx, cam_name in enumerate(self.cam_dict):
            cam = self.cam_dict[cam_name]
            cam.frame = np.zeros(cam.shape, dtype="ubyte")
            cam.frameBuff[0:] = np.frombuffer(cam.array4feed.get_obj(), self.dtype, cam.size)
            dimensions = self.cam_crop.croproi[ndx] if self.crop else cam.frame_dims

            new_dims = FrameDims(
                x1=dimensions[0],
                x2=dimensions[0] + dimensions[1],
                y1=dimensions[2],
                y2=dimensions[2] + dimensions[3],
                h=dimensions[3],
                w=dimensions[1],
                dispSize=dimensions[3] * dimensions[1] * 3,
            )

            frame = cam.frameBuff[0 : new_dims.dispSize].reshape([new_dims.h, new_dims.w, 3])
            frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
            for f in range(3):
                cam.frame[new_dims.y1 : new_dims.y2, new_dims.x1 : new_dims.x2, f] = frame[:, :, f]
            cam.frame_size = new_dims

        self.im[0].set_data(self.cam_dict[list(self.cam_dict)[self.cam_pointer]].frame)
        self.im[1].set_data(self.cam_dict[list(self.cam_dict)[self.cam_pointer + 1]].frame)
        return True

    def deinitialize(self):
        self.serial.close()

        for ndx, im in enumerate(self.im):
            frame = np.zeros(self.cam_dict[list(self.cam_dict)[ndx]].shape, dtype="ubyte")
            im.set_data(frame)
            self.cam_crop.croprec[ndx].set_alpha(0)

        self.deinitThreads()

    def camReset(self, event):
        self.initThreads()
        self.camaq.value = 2
        self.startAq()
        time.sleep(3)
        self.stopAq()
        self.deinitThreads()
        logger.info("\n*** CAMERAS RESET ***\n")

    def live_start(self):
        self.camaq.value = 1
        self.startAq()

    def live_stop(self):
        self.stopAq()
        time.sleep(2)

    def vidPlayer(self, event):
        if self.camaq.value == 2:
            return
        self.participant_monitor.update_screen()
        for ndx, cam in enumerate(self.cam_dict.values()):
            if cam.frmGrab.value == 1:
                cam.frameBuff[0:] = np.frombuffer(cam.array4feed.get_obj(), self.dtype, cam.size)
                dims = cam.frame_size
                frame = cam.frameBuff[0 : dims.dispSize].reshape([dims.h, dims.w, 3])
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                for f in range(3):
                    cam.frame[dims.y1 : dims.y2, dims.x1 : dims.x2, f] = frame[:, :, f]
                cam.frame_size = dims

                if ndx == self.cam_pointer:
                    self.im[0].set_data(cam.frame)
                elif ndx == self.cam_pointer + 1:
                    self.im[1].set_data(cam.frame)
                cam.frmGrab.value = 0

                if self.hardware_test:
                    cam.cam_tests = np.roll(cam.cam_tests, 1)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
                    variance = laplacian.var()
                    cam.cam_tests[0] = variance

                    normalized_img = gray / 255.0
                    # Calculate RMS contrast (Standard Deviation)
                    rms = np.std(normalized_img)
                    cam.contrast_tests = np.roll(cam.contrast_tests, 1)
                    cam.contrast_tests[0] = rms
        if self.hardware_test:
            if self.focus_test.GetValue():
                self.update_focus()
            elif self.contrast_test.GetValue():
                self.update_contrast()
        self.figure.canvas.draw()

    def update_focus(self, plot=True):
        if plot:
            cam_list = []
            for cam in self.cam_dict.values():
                cam_list.append(cam.cam_tests)
            self.ctrl_panel.plot_hardware(cam_list, 300)
        else:
            for cam in self.cam_dict.values():
                cam.cam_tests = np.full(shape=30 * 2, fill_value=np.nan)

    def update_contrast(self, plot=True):
        if plot:
            cam_list = []
            for cam in self.cam_dict.values():
                cam_list.append(cam.contrast_tests)
            self.ctrl_panel.plot_hardware(cam_list, 1)
        else:
            for cam in self.cam_dict.values():
                cam.cam_tests = np.full(shape=30 * 2, fill_value=np.nan)

    def start_recording(self, event, base_dir, sess_dir, path_base, count):
        totTime = 20  # int(self.secRec.GetValue())+int(self.minRec.GetValue())*60
        spaceneeded = 0
        freespace = shutil.disk_usage(base_dir)[2]
        for ndx, cam in enumerate(self.cam_dict.values()):
            recSize = self.aqW[ndx] * self.aqH[ndx] * 3 * cam.actual_framerate * totTime
            spaceneeded += recSize
        if spaceneeded > freespace:
            self.warning.update_error(WarnCat.SPACE).display()

        logger.info(f"Total estimated run time: {totTime}")
        for cam in self.cam_dict.values():
            cam.camq.put(CameraCommand.RECORD_PREP)
            name_base = "%s_%s_trial%03d" % (path_base, cam.name, count)
            new_base = os.path.join(sess_dir, name_base)
            cam.camq.put(new_base)
            cam.camq_p2read.get()

        self.camaq.value = 1
        self.startAq()

    def stop_recording(self, event):
        self.shared.value = -1
        self.stopAq()
        time.sleep(2)

    def initThreads(self):
        logger.verbose("initThreads started")
        self.multi_cameras.clear()
        for camID, cam_d in self.cam_dict.items():
            multi_cam = spin.multiCam_DLC_Cam(
                cam_d.camq,
                cam_d.camq_p2read,
                camID,
                list(self.cam_dict),
                cam_d.frame_dims,
                self.camaq,
                self.frmaq,
                cam_d.array4feed,
                cam_d.frmGrab,
                DOWNSAMPLE_VAL,
                rcp_context=self._rcp_context,
            )
            self.multi_cameras.append(multi_cam)
            multi_cam.start()
        time.sleep(1)
        for cam in self.cam_dict.values():
            initialization = CameraCommand.INIT_M if cam.is_primary else CameraCommand.INIT_S
            cam.camq.put(initialization)
            cam.camq_p2read.get()

    def deinitThreads(self):
        logger.verbose("deinitThreads started")
        for n, cam in enumerate(self.cam_dict.values()):
            cam.camq.put(CameraCommand.RELEASE)
            try:
                cam.camq_p2read.get(timeout=3)
            except queue.Empty:
                logger.warning("timeout get from p2read")
            cam.camq.close()
            cam.camq_p2read.close()
            self.multi_cameras[n].terminate()

    def startAq(self):
        logger.verbose("startAq started")
        if self.serial.serSuccess:
            msg = f"S{self.session}x{self.trial}x"
            self.serial.write(msg)

        if self.camaq.value < 2:
            self.camaq.value = 1

        for cam in self.cam_dict.values():
            cam.camq.put(CameraCommand.START)
        for prim_cam_name in self.primary_cams:
            self.cam_dict[prim_cam_name].camq.put(CameraCommand.TRIG_OFF)

    def stopAq(self):
        logger.verbose("stopAq started")
        if self.serial.serSuccess:
            msg = "Xx"
            self.serial.ser.write(msg.encode())
        error_message = []
        video_errors = []
        self.camaq.value = 0
        threshold = 1
        for camID in self.secondary_cams:
            cam_d = self.cam_dict[camID]
            cam_d.camq.put(CameraCommand.STOP)
            update = cam_d.camq_p2read.get()
            if update != "done":
                if int(update) > threshold:
                    error_message.append(f"{update}% of camera frames dropped for {camID}")
                cam_d.camq_p2read.get()
        for camID in self.primary_cams:
            cam_d = self.cam_dict[camID]
            cam_d.camq.put(CameraCommand.STOP)
            update = cam_d.camq_p2read.get()
            if update != "done":
                if int(update) > threshold:
                    error_message.append(f"{update}% of camera frames dropped for {camID}")
                cam_d.camq_p2read.get()
        logger.warning(error_message)
        error = ""
        if video_errors:
            error = "\n" + "\n".join(video_errors)
        if error_message:
            if error == "":
                error += "\n"
            error += "\n" + "\n".join(error_message)
        if error != "":
            self.warning.update_error(WarnCat.FRAMES, info=error).display()

    def updateSettings(self, event):
        self.aqW = []
        self.aqH = []
        self.recSet = []
        for n, camID in enumerate(self.cam_dict):
            cam_d = self.cam_dict[camID]
            cam_d.camq.put(CameraCommand.UPDATE_SETTINGS)
            suc_test = cam_d.camq_p2read.get()
            if suc_test == -1:
                raise ValueError("Cameras unresponsive")
            message = "crop" if self.crop else "full"
            cam_d.camq.put(message)

            # self.recSet.append(self.cam_dict[camID].camq_p2read.get())
            self.aqW.append(cam_d.camq_p2read.get())
            self.aqH.append(cam_d.camq_p2read.get())

    def get_exposure(self, event):
        for n, cam_d in enumerate(self.cam_dict.values()):
            cam_d.camq.put(CameraCommand.SET_EXPOSURE)
        self.startAq()
        self.camaq.value = 1
        time.sleep(1)
        self.camaq.value = 0
        self.stopAq()
        for n, cam_d in enumerate(self.cam_dict.values()):
            cam_d.camq.put(CameraCommand.GET_EXPOSURE)
            cam_d.exposure = cam_d.camq_p2read.get()

        for n, cam_d in enumerate(self.cam_dict.values()):
            cam_d.camq.put(CameraCommand.SET_BALANCE)
        self.startAq()
        self.camaq.value = 1
        time.sleep(1)
        self.camaq.value = 0
        self.stopAq()
        primary_rate = self.framerate
        if len(self.primary_cams) <= 1:
            self.cam_dict[self.primary_cams[0]].camq.put(CameraCommand.GET_BALANCE)
            rate = self.cam_dict[self.primary_cams[0]].camq_p2read.get()
            primary_rate = self.cam_dict[self.primary_cams[0]].actual_framerate = rate
        for n, cam_d in enumerate(self.cam_dict.values()):
            if not cam_d.is_primary:
                cam_d.actual_framerate = primary_rate / int(cam_d.decrease_val)
                cam_d.camq.put(CameraCommand.GET_BALANCE)

    def update_crop(self, value):
        self.crop = value

    def update_cameras_viewed(self, event):
        # switching which 2 cameras are seen
        if self.cam_pointer + 2 >= len(self.cam_dict):
            self.cam_pointer = 0
        else:
            self.cam_pointer += 2

        cam1 = self.cam_dict[list(self.cam_dict)[self.cam_pointer]]

        self.im[0].set_data(cam1.frame)

        if not (len(self.cam_dict) <= self.cam_pointer + 1):
            cam2 = self.cam_dict[list(self.cam_dict)[self.cam_pointer + 1]]
            self.im[1].set_data(cam2.frame)
            cam2_name = cam2.name
        else:
            cam2_name = ""
            self.im[1].set_data(np.zeros(cam1.shape, dtype="ubyte"))

        self.image_panel.update_names([cam1.name, cam2_name])

    def reset_variables(self):
        self.labjack_scan_rate = None
        self.secondary_cams = []
        self.primary_cams = []
        self.cam_pointer = 0
        self.im = []
        self.x1 = 0
        self.y1 = 0
        self.shared.value = 0
        self.camaq.value = 0
        self.frmaq.value = 0
        self.crop = True
        self.hardware_test = True
