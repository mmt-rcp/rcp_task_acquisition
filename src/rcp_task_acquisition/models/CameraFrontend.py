import ctypes
import os
import queue
import shutil
import time
from multiprocessing import Array, Queue, Value
from pathlib import Path
from typing import Callable

import cv2
import numpy as np
import wx
from matplotlib.image import AxesImage

import rcp_task_acquisition.models.CameraProcess as spin
from rcp_task_acquisition.algo import put_to_algo
from rcp_task_acquisition.gui import call_in_gui
from rcp_task_acquisition.models.CameraProcess import CameraCommand
from rcp_task_acquisition.models.Crop import Crop
from rcp_task_acquisition.models.SerialDevice import SerialDevice
from rcp_task_acquisition.models.Warnings import WarnCat, WarningHandler
from rcp_task_acquisition.panels.GraphPanel import GraphPanel
from rcp_task_acquisition.panels.ImagePanel import ImagePanel
from rcp_task_acquisition.panels.ParticipantMonitorPanel import MonitorPanel
from rcp_task_acquisition.utils import config
from rcp_task_acquisition.utils.camera_settings import FrameDims, CamSettings
from rcp_task_acquisition.utils.constants import CAM_MAX_HEIGHT, CAM_MAX_WIDTH, DOWNSAMPLE_VAL
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.run_context import RcpRunContext
from rcp_task_acquisition.utils.typing import MaybeOkCallback

logger = get_logger(__name__)


class CamerasFrontend:
    def __init__(
        self,
        serial: SerialDevice,
        panel: GraphPanel,
        image_panel: ImagePanel,
        monitor: MonitorPanel,
        *,
        rcp_context: RcpRunContext,
    ):
        self._rcp_context = rcp_context
        self.serial = serial
        # self.shared = Value(ctypes.c_byte, 0) unused
        self.camaq = Value(ctypes.c_byte, 0)
        self.frmaq = Value(ctypes.c_int, 0)
        self.reset_variables()
        self.dtype = "uint8"
        self.cam_crop = Crop()
        self.ctrl_panel = panel
        self.image_panel = image_panel
        self.warning = WarningHandler()
        self.trial = 0
        self.session = 0
        self.participant_monitor = monitor
        self.framerate: float = 0
        self.crop = False
        self.cam_dict: dict[str, CamSettings] = {}  # key is cam serial
        # NB: cam_dict is used from MainFrame
        self._cam_by_idx: list[CamSettings] = []
        self.multi_cameras: dict[str, spin.multiCam_DLC_Cam] = {}  # key is cam serial
        #
        self.labjack_scan_rate = None
        self.primary_cams: list[str] = []  # cam serial
        self.secondary_cams: list[str] = []  # cam serial
        self.cam_pointer = 0
        self.im: list[AxesImage] = []
        self.x1 = 0
        self.y1 = 0
        # self.shared.value = 0
        self.camaq.value = 0
        self.frmaq.value = 0
        self.crop = True
        self.hardware_test = True
        self._cams_cfg = config.CamerasDictConfig()
        self._is_unconnected = True
        self.aqW: list[int] = []  # cameras width
        self.aqH: list[int] = []  # cameras height

    @property
    def camera_settings(self) -> list[CamSettings]:
        return self._cam_by_idx

    def get_camera_by_index(self, idx: int) -> CamSettings:
        return self._cam_by_idx[idx]

    def setup(
        self,
        cams_cfg: config.CamerasDictConfig,
        is_unconnected: bool,
        requested_framerate: float,
    ) -> None:
        logger.info("Camera.setup: cams_cfg: %s", cams_cfg)
        self._cams_cfg = cams_cfg
        self._is_unconnected = is_unconnected
        self.framerate = requested_framerate

    def _prepare_cams(self) -> None:
        self.cam_crop = Crop()
        self.reset_variables()
        self.cam_dict.clear()
        self._cam_by_idx.clear()

        cam_idx = -1
        for cam_item, cfg in self._cams_cfg.items():
            name = cam_item.value
            if not cfg.in_use:
                logger.debug("skipping %s not in_use", cam_item)
                continue

            cam_idx += 1
            cam_bin = int(cfg.bin)
            cam_dims = (
                0,
                int(CAM_MAX_HEIGHT / DOWNSAMPLE_VAL / cam_bin),
                0,
                int(CAM_MAX_WIDTH / DOWNSAMPLE_VAL / cam_bin),
            )
            is_primary = bool(cfg.ismaster or self._is_unconnected)
            new_cam = CamSettings(
                idx=cam_idx,
                name=name,
                cam_item=cam_item,
                serial=cfg.serial,
                is_primary=is_primary,
                size=cam_dims[1] * cam_dims[3] * 3,
                shape=[cam_dims[1], cam_dims[3], 3],
                bin_val=cam_bin,
                frame_dims=cam_dims,
                decrease_val=int(cfg.framerate_decrease_factor),
                actual_framerate=0,
                exposure=None,
                cam_tests=np.full(shape=30 * 2, fill_value=np.nan),
                contrast_tests=np.full(shape=30 * 2, fill_value=np.nan),
                frame=np.zeros([cam_dims[1], cam_dims[3], 3], dtype="ubyte"),
                frameBuff=np.zeros(cam_dims[1] * cam_dims[3] * 3, dtype="ubyte"),
                array4feed=Array(ctypes.c_ubyte, cam_dims[1] * cam_dims[3] * 3),
                frmGrab=Value(ctypes.c_byte, 0),
                camq=Queue(
                    maxsize=32
                ),  # cameras are supposed to read fast, and only write on demand,
                camq_p2read=Queue(maxsize=32),  # on their input/output queues.
                frame_size=FrameDims(),
                base_config=cfg,
            )
            self.cam_dict[new_cam.serial] = new_cam
            self._cam_by_idx.append(new_cam)

            self.cam_crop.add_crop(cfg.crop)
            if cfg.ismaster or self._is_unconnected:
                self.primary_cams.append(new_cam.serial)
            else:
                self.secondary_cams.append(new_cam.serial)

        camCt = len(self.cam_dict)
        cam_names = [cam.name for cam in self._cam_by_idx]
        self.ctrl_panel.hardware_test(30 * 2, camCt, cam_names)

        cam0, cam1 = self._cam_by_idx[self.cam_pointer : self.cam_pointer + 2]
        for cam in (cam0, cam1):
            axe = self.image_panel.axes[cam.idx]
            im_d = axe.imshow(cam.frame)
            im_d.set_clim(0, 255)
            self.im.append(im_d)
            self.cam_crop.update_crop(cam.idx, axe, cam.frame_dims)
        self.image_panel.update_names([cam0.name, cam1.name])
        self.image_panel.draw()

    @put_to_algo
    def initialize(self, *, callback: MaybeOkCallback = None) -> bool:
        try:
            return self._initialize(callback=callback)
        except BaseException as err:
            logger.exception("Error intialize: %s", err)
            if callback:
                callback(err)
            return False

    def _initialize(self, *, callback: MaybeOkCallback = None) -> bool:
        self.serial.init_serial()
        self.initThreads()
        try:
            self.updateSettings()
        except Exception as err:
            # NB: normally we don't need anymore this, at least for valid settings
            logger.exception("Error updating settings: %s", err)
            # logger.info("Trying to fix cameras. Please wait...")
            # self.deinitThreads()
            # self.camReset()
            # self.initThreads()
            # try:
            #     self.updateSettings()
            # except Exception as err:
            #     logger.exception("Error reupdating settings: %s", err)
            #     return False
            if callback is not None:
                callback(err)
            return False
        self.get_exposure()
        self.updateSettings()  # reapplied ??
        self.camaq.value = 1
        self.startAq()
        time.sleep(0.5)
        self.camaq.value = 0
        self.stopAq()

        for cam in self._cam_by_idx:
            cam.frame = np.zeros(cam.shape, dtype="ubyte")
            cam.frameBuff[0:] = np.frombuffer(cam.array4feed.get_obj(), self.dtype, cam.size)
            dimensions = self.cam_crop.croproi[cam.idx] if self.crop else cam.frame_dims

            new_dims = FrameDims(
                x1=dimensions[0],
                x2=dimensions[0] + dimensions[1],
                y1=dimensions[2],
                y2=dimensions[2] + dimensions[3],
                h=dimensions[3],
                w=dimensions[1],
                dispSize=dimensions[3] * dimensions[1] * 3,
            )

            cam.apply_new_dims(new_dims)
        self._apply_cam_data()
        if callback is not None:
            callback(None)
        return True

    @call_in_gui
    def _apply_cam_data(self):
        cam0, cam1 = self._cam_by_idx[self.cam_pointer : self.cam_pointer + 2]
        self.im[0].set_data(cam0.frame)
        self.im[1].set_data(cam1.frame)

    def deinitialize(self) -> None:
        self.serial.close()

        for ndx, im in enumerate(self.im):
            cam_s = self._cam_by_idx[ndx]
            im.set_data(np.zeros(cam_s.shape, dtype="ubyte"))
            self.cam_crop.croprec[ndx].set_alpha(0)

        self.deinitThreads()

    def camReset(self) -> None:
        self.initThreads()
        self.camaq.value = 2
        self.startAq()
        time.sleep(1.5)
        try:
            self.stopAq()
        except Exception as err:
            logger.verbose("stopAq: %s", err)
        self.deinitThreads()
        logger.info("\n*** CAMERAS RESET ***\n")

    def live_start(self) -> None:
        self.camaq.value = 1
        self.startAq()

    def live_stop(self) -> None:
        self.stopAq()
        # time.sleep(2)

    def on_cam_update(self, cam: CamSettings, frame: np.ndarray) -> None:
        redraw = False
        if cam.idx == self.cam_pointer:
            self.im[0].set_data(frame)
            redraw = True
        elif cam.idx == self.cam_pointer + 1:
            self.im[1].set_data(frame)
            redraw = True
        #
        if self.hardware_test:
            redraw = True
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
        if redraw:
            self.image_panel.figure.canvas.draw()

    def vidPlayer(self, event: wx.Event) -> None:
        # logger.debug("vidPlayer: %s", event)
        if self.camaq.value == 2:
            return
        # self.participant_monitor.update_screen()
        # already done in separate timer
        if self.hardware_test:
            if self.ctrl_panel.focus_test.GetValue():
                self.update_focus()
            elif self.ctrl_panel.contrast_test.GetValue():
                self.update_contrast()
        # self.image_panel.figure.canvas.draw()

    def update_focus(self, plot: bool = True) -> None:
        if plot:
            cam_list = []
            for cam in self._cam_by_idx:
                cam_list.append(cam.cam_tests)
            self.ctrl_panel.plot_hardware(cam_list, 300)
        else:
            for cam in self._cam_by_idx:
                cam.cam_tests = np.full(shape=30 * 2, fill_value=np.nan)

    def update_contrast(self, plot: bool = True) -> None:
        if plot:
            cam_list = []
            for cam in self._cam_by_idx:
                cam_list.append(cam.contrast_tests)
            self.ctrl_panel.plot_hardware(cam_list, 1)
        else:
            for cam in self._cam_by_idx:
                cam.cam_tests = np.full(shape=30 * 2, fill_value=np.nan)

    def start_recording(self, base_dir: Path, sess_dir: Path, path_base: str, count: int) -> None:
        totTime: float = 20  # int(self.secRec.GetValue())+int(self.minRec.GetValue())*60
        spaceneeded: float = 0
        freespace = shutil.disk_usage(base_dir)[2]
        for cam in self._cam_by_idx:
            recSize = self.aqW[cam.idx] * self.aqH[cam.idx] * 3 * cam.actual_framerate * totTime
            spaceneeded += recSize
        if spaceneeded > freespace:
            self.warning.update_error(WarnCat.SPACE).display()

        logger.info("Total estimated run time: %s", totTime)
        for cam in self._cam_by_idx:
            name_base = "%s_%s_trial%03d" % (path_base, cam.name, count)
            new_base = os.path.join(sess_dir, name_base)
            cam.put_to(CameraCommand.RECORD_PREP)
            cam.put_to(new_base, timeout=1)
            res = cam.get_from(timeout=3)
            logger.verbose("RECORD_PREP res: %s", res)

        self.camaq.value = 1
        self.startAq()

    def stop_recording(self) -> None:
        # self.shared.value = -1
        self.stopAq()
        time.sleep(2)

    def initThreads(self) -> None:
        logger.verbose("initThreads started")
        self._prepare_cams()
        self.multi_cameras.clear()
        all_cams_serial = [c.serial for c in self._cam_by_idx]
        for cam_d in self._cam_by_idx:
            multi_cam = spin.multiCam_DLC_Cam(
                cam_d,
                all_cams_serial,
                self.camaq,
                self.frmaq,
                DOWNSAMPLE_VAL,
                user_config=self._rcp_context.user_config,
            )
            self.multi_cameras[cam_d.serial] = multi_cam
            multi_cam.start()
        # time.sleep(1)
        logger.notice("Starting initialisation of cameras")
        for cam in self._cam_by_idx:
            initialization = CameraCommand.INIT_M if cam.is_primary else CameraCommand.INIT_S
            try:
                cam.put_to(initialization, timeout=1)
                res = cam.get_from(timeout=5)  # initialisation can be slow somtimes
            except Exception as err:
                logger.error("%s: cannot initialize camera: %s", cam.name, err)
                raise
            else:
                logger.debug("%s: init response: %s", cam.name, res)

    def deinitThreads(self) -> None:
        logger.verbose("deinitThreads started")
        errors = {}
        for cam in self._cam_by_idx:
            try:
                cam.put_to(CameraCommand.RELEASE, timeout=0)
            except Exception as err:
                errors[cam.serial] = err
        for cam in self._cam_by_idx:
            try:
                ret = cam.get_from(timeout=3)
            except queue.Empty:
                logger.warning("timeout get from p2read")
            except Exception as err:
                errors[cam.serial] = err
            else:
                logger.debug("%s: received response: %s", cam.name, ret)
                try:
                    cam.put_to(None, timeout=0)
                except Exception as err:
                    logger.warning("%s: timeout put to: %s", cam.name, err)
        for multi_cam in self.multi_cameras.values():
            logger.debug("terminating %s", multi_cam.name)
            multi_cam.terminate()
            multi_cam.join(1)
        for cam in self._cam_by_idx:
            cam.camq.close()
            cam.camq_p2read.close()
        for multi_cam in self.multi_cameras.values():
            if multi_cam.is_alive():
                logger.debug("killing %s", multi_cam.name)
                multi_cam.kill()
                multi_cam.join(1)
        self.cam_dict.clear()
        self.multi_cameras.clear()
        self._cam_by_idx.clear()
        logger.info("all cameras stopped")

    def startAq(self) -> None:
        logger.verbose("startAq started")
        if self.serial.serSuccess:
            msg = f"S{self.session}x{self.trial}x"
            self.serial.write(msg)

        if self.camaq.value < 2:
            self.camaq.value = 1

        for cam in self._cam_by_idx:
            cam.put_to(CameraCommand.START, timeout=1)
        for prim_cam_serial in self.primary_cams:
            cam = self.cam_dict[prim_cam_serial]
            cam.put_to(CameraCommand.TRIG_OFF, timeout=1)

    def stopAq(self) -> None:
        logger.verbose("stopAq started")
        if self.serial.serSuccess:
            msg = "Xx"
            self.serial.write(msg)
        error_message: list[str] = []
        self.camaq.value = 0
        threshold = 1

        def request_cam_stop_send(cam_id: str):
            cam_d = self.cam_dict.get(cam_id)
            if cam_d is None:
                return
            logger.verbose("requesting camera stop to %s", cam_d.name)
            cam_d.put_to(CameraCommand.STOP, timeout=1)

        def request_cam_stop_recv(cam_id: str):
            cam_d = self.cam_dict.get(cam_id)
            if cam_d is None:
                return
            ret = cam_d.get_from(timeout=3)
            logger.debug("received rsp = %r from cam", ret)
            if ret != "done":
                if isinstance(ret, int):
                    if ret > threshold:
                        error_message.append(f"{ret}% of camera frames dropped for {cam_d.name}")
                    ret = cam_d.get_from(timeout=1)
                    if ret != "done":
                        logger.warning("%s: unexpected response to cam stop: %s", cam_d.name, ret)
                else:
                    logger.warning("%s: unexpected rsp for STOP: %s", cam_d.name, ret)

        cam_errors = {}
        for camID in self.secondary_cams:
            try:
                request_cam_stop_send(camID)
            except Exception as err:
                cam_errors[camID] = err

        for camID in self.secondary_cams:
            try:
                request_cam_stop_recv(camID)
            except Exception as err:
                cam_errors[camID] = err

        for camID in self.primary_cams:
            try:
                request_cam_stop_send(camID)
                request_cam_stop_recv(camID)
            except Exception as err:
                cam_errors[camID] = err

        error = ""
        if error_message:
            if error == "":
                error += "\n"
            error += "\n" + "\n".join(error_message)
        if error != "":
            self.warning.update_error(WarnCat.FRAMES, info=error).display()
        # NB:
        # don't raise errors. callers expect action to succeed always. unless interrupted or such.

    def updateSettings(self) -> None:
        self.aqH = [0] * len(self._cam_by_idx)
        self.aqW = [0] * len(self._cam_by_idx)
        aqH = []
        aqW = []
        errors = {}
        for cam_d in self._cam_by_idx:
            try:
                cam_d.put_to(CameraCommand.UPDATE_SETTINGS, timeout=1)
                ret = cam_d.get_from(timeout=2)
                if ret != "done":
                    raise RuntimeError(f"camera failed: {ret}")
            except Exception as err:
                logger.error("%s: could not update settings: %s", cam_d.name, err)
                errors[cam_d.name] = err
                aqW.append(0)
                aqH.append(0)
                continue
                # raise ValueError("Cameras unresponsive")
            message = "crop" if self.crop else "full"
            cam_d.put_to(message, timeout=1)
            # self.recSet.append(self.cam_dict[camID].get_from())
            try:
                width, height = cam_d.get_from(timeout=2)
            except Exception as err:
                logger.error("could not read W/H: %s", err)
                errors[cam_d.name] = err
                aqW.append(0)
                aqH.append(0)
            else:
                aqW.append(width)
                aqH.append(height)
        self.aqW = aqW
        self.aqH = aqH
        if errors:
            raise RuntimeError(f"{errors}")

    def get_exposure(self) -> None:
        for cam_d in self._cam_by_idx:
            cam_d.put_to(CameraCommand.SET_EXPOSURE, timeout=1)
        self.startAq()
        self.camaq.value = 1
        time.sleep(1)
        self.camaq.value = 0
        self.stopAq()
        for cam_d in self._cam_by_idx:
            cam_d.put_to(CameraCommand.GET_EXPOSURE, timeout=1)
        for cam_d in self._cam_by_idx:
            cam_d.exposure = cam_d.get_from(timeout=2)

        for cam_d in self._cam_by_idx:
            cam_d.put_to(CameraCommand.SET_BALANCE, timeout=1)
        self.startAq()
        self.camaq.value = 1
        time.sleep(1)
        self.camaq.value = 0
        self.stopAq()
        primary_rate = self.framerate
        if len(self.primary_cams) >= 1:
            prim_cam = self.cam_dict[self.primary_cams[0]]
            prim_cam.put_to(CameraCommand.GET_BALANCE, timeout=1)
            rate = prim_cam.get_from(timeout=2)
            logger.verbose("receive rate: %r", rate)
            if isinstance(rate, (int, float)):
                primary_rate = prim_cam.actual_framerate = rate
        for cam_d in self._cam_by_idx:
            if not cam_d.is_primary:
                cam_d.actual_framerate = primary_rate / int(cam_d.decrease_val)
                cam_d.put_to(CameraCommand.GET_BALANCE, timeout=2)

    def update_crop(self, value) -> None:
        self.crop = value

    def update_cameras_viewed(self, event: wx.Event) -> None:
        # switching which 2 cameras are seen
        if self.cam_pointer + 2 >= len(self.cam_dict):
            self.cam_pointer = 0
        else:
            self.cam_pointer += 2

        cam1 = self._cam_by_idx[self.cam_pointer]

        self.im[0].set_data(cam1.frame)

        if len(self.cam_dict) > self.cam_pointer + 1:
            cam2 = self._cam_by_idx[self.cam_pointer + 1]
            self.im[1].set_data(cam2.frame)
            cam2_name = cam2.name
        else:
            cam2_name = ""
            self.im[1].set_data(np.zeros(cam1.shape, dtype="ubyte"))

        self.image_panel.update_names([cam1.name, cam2_name])

    def reset_variables(self) -> None:
        self.labjack_scan_rate = None
        self.secondary_cams = []
        self.primary_cams = []
        self.cam_pointer = 0
        self.im = []
        self.x1 = 0
        self.y1 = 0
        # self.shared.value = 0
        self.camaq.value = 0
        self.frmaq.value = 0
        self.crop = True
        self.hardware_test = True
