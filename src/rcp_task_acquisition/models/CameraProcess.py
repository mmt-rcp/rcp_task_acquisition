import enum
import multiprocessing
from collections.abc import Callable
from math import floor
from queue import Empty

import cv2
import numpy as np
import PySpin

from rcp_task_acquisition.models.AsyncVideoWriter import AsyncFFmpegGPUWriter  # AsyncVideoWriter
from rcp_task_acquisition.utils.camera_utils import identify_dropped_frames
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.multiprocess import ProcessWithLogging
from rcp_task_acquisition.utils.run_context import RcpRunContext
from rcp_task_acquisition.utils.typing import SharedArray, SharedInt

logger = get_logger(__name__)


class CameraCommand(str, enum.Enum):
    UPDATE_SETTINGS = "updateSettings"
    INIT_M = "InitM"
    INIT_S = "InitS"
    INIT_C = "InitC"  # unused atm
    RELEASE = "Release"
    RECORD_PREP = "recordPrep"
    START = "Start"
    STOP = "Stop"  # not implemented !!
    SET_EXPOSURE = "setExposure"
    GET_EXPOSURE = "getExposure"
    SET_BALANCE = "setBalance"
    GET_BALANCE = "getBalance"
    TRIG_OFF = "TrigOff"  # not implemented !!


class CamCtx:
    record = False
    ismaster = False
    isunconnected = False
    is_decreased = False
    record_frame_rate: float = 0
    cam_list: PySpin.CameraList
    cam: PySpin.Camera
    system: PySpin.SystemPtr
    processor: PySpin.ImageProcessor
    aqW: int
    aqH: int
    frameSml: np.ndarray
    camStr: str = ""
    method: str = "none"
    file_path: str = ""
    current_exposure_time: float = 0
    max_exposure: float = 0
    frmrate_time_to_set: float = 0
    start_time: float = 0
    capture_duration: float = 0


class multiCam_DLC_Cam(ProcessWithLogging):
    def __init__(
        self,
        camq: multiprocessing.Queue,
        camq_p2read: multiprocessing.Queue,
        camID: str,
        idList: list[str],
        frmdim: list[int],
        aq: SharedInt,
        frm: SharedInt,
        array4feed: SharedArray,
        frmGrab: SharedInt,
        dwnsmplfac: int,
        *,
        rcp_context: RcpRunContext,
    ):
        super().__init__()
        self._rcp_context = rcp_context
        self.camID = camID
        self.camq = camq
        self.camq_p2read = camq_p2read
        self.idList = idList
        self.frmdim = frmdim
        self.aq = aq
        self.frm = frm
        self.array4feed = array4feed
        self.frmGrab = frmGrab
        self.framerate: float = 0
        # self.actual_exposure = None
        # self.actual_frame_rate = None
        # self.video_thread = None
        self.fps: float = 0
        self.width: int = 0
        self.height: int = 0
        self.dwnsmplfac = dwnsmplfac

        self._command_handlers: dict[str, Callable] = {
            CameraCommand.INIT_S: self._cmd_InitS,
            CameraCommand.INIT_C: self._cmd_InitC,
            CameraCommand.INIT_M: self._cmd_InitM,
            CameraCommand.UPDATE_SETTINGS: self._cmd_updateSettings,
            CameraCommand.GET_EXPOSURE: self._cmd_getExposure,
            CameraCommand.GET_BALANCE: self._cmd_getBalance,
            CameraCommand.START: self._cmd_Start,
            CameraCommand.SET_EXPOSURE: self._cmd_setExposure,
            CameraCommand.SET_BALANCE: self._cmd_setBalance,
            CameraCommand.RELEASE: self._cmd_Release,
            CameraCommand.TRIG_OFF: self._cmd_TrigOff,
            CameraCommand.STOP: self._cmd_Stop,
            CameraCommand.RECORD_PREP: self._cmd_recordPrep,
        }

    def run(self) -> None:
        ctx = CamCtx()
        # exposure_max = 4000
        user_config = self._rcp_context.user_config
        cams_cfg = user_config.cameras
        camStr = None
        for name, cfg in cams_cfg.items():
            if not cfg.in_use:
                continue
            if self.camID == cfg.serial:
                camStr = name
        if camStr is None:
            logger.error("cam serial not found")
            return
        assert isinstance(camStr, str)
        # logger.debug(camStr)
        ctx.camStr = camStr
        # camCt = len(self.camStrList)
        cfg = cams_cfg[camStr]
        framerate_decrease = cfg.framerate_decrease_factor
        if framerate_decrease != 1:
            ctx.is_decreased = True
        # if gig_e:
        self.framerate = round(user_config.cam_config.framerate / framerate_decrease)
        # else:
        ctx.current_exposure_time = 1000  # = int(user_cfg[camStr]['exposure'])

        ctx.aqW = int(cfg.crop[1] * self.dwnsmplfac)
        ctx.aqH = int(cfg.crop[3] * self.dwnsmplfac)

        # frame_results = np.zeros([int(self.frmdim[1]*self.dwnsmplfac),int(self.frmdim[3]*self.dwnsmplfac),3],'ubyte')
        # frame_results = np.zeros([aqH,aqW,3],'ubyte')
        ctx.frameSml = np.zeros(
            [
                int(ctx.aqH / self.dwnsmplfac / cfg.bin),
                int(ctx.aqW / self.dwnsmplfac / cfg.bin),
                3,
            ],
            "ubyte",
        )

        ctx.method = "none"
        ctx.system = PySpin.System.GetInstance()

        ctx.cam_list = ctx.system.GetCameras()
        ctx.cam = ctx.cam_list.GetBySerial(self.camID)
        ctx.processor = PySpin.ImageProcessor()
        ctx.processor.SetColorProcessing(PySpin.SPINNAKER_COLOR_PROCESSING_ALGORITHM_HQ_LINEAR)
        while True:
            try:  # get a new msg command
                msg = self.camq.get(timeout=0.5)  # using 0.5s wait timeout,
                # could even use more, given nothing else to check/wait on here.
            except Empty:
                continue

            logger.debug(f"{camStr} msg: {msg}")
            handle = self._command_handlers.get(msg, None)  # type: ignore
            if handle is None:
                logger.warning("Unhandled command: %s", msg)
                continue

            try:
                handle(ctx)
            except PySpin.SpinnakerException as err:
                logger.exception("%s: failed executing %s: %s", camStr, msg, err)
                if msg == CameraCommand.UPDATE_SETTINGS:
                    self.camq_p2read.put(-1)
                    self.camq_p2read.put(30)
                    self.camq_p2read.put(30)
                else:
                    self.camq_p2read.put("done")

    def _cmd_InitM(self, ctx: CamCtx) -> None:
        ctx.ismaster = True
        cam = ctx.cam
        cam.Init()
        self.create_primary(cam)
        self.camq_p2read.put("done")
        while cam.TLStream.StreamOutputBufferCount() > 0:
            _image = cam.GetNextImage(100)
            _image.Release()

    def _cmd_InitS(self, ctx: CamCtx) -> None:
        cam = ctx.cam
        cam.Init()
        self.create_secondary(cam, ctx.is_decreased)
        self.camq_p2read.put("done")
        while cam.TLStream.StreamOutputBufferCount() > 0:
            _image = cam.GetNextImage(100)
            _image.Release()

    def _cmd_InitC(self, ctx: CamCtx) -> None:
        cam = ctx.cam
        cam.Init()
        cam.LineSelector.SetValue(PySpin.LineSelector_Line2)
        cam.V3_3Enable.SetValue(False)
        cam.LineSelector.SetValue(PySpin.LineSelector_Line1)
        cam.LineSource.SetValue(PySpin.LineSource_ExposureActive)
        cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)
        cam.TriggerSource.SetValue(PySpin.TriggerSource_Software)
        cam.TriggerOverlap.SetValue(PySpin.TriggerOverlap_Off)
        cam.TriggerMode.SetValue(PySpin.TriggerMode_On)
        ctx.isunconnected = True
        while cam.TLStream.StreamOutputBufferCount() > 0:
            _image = cam.GetNextImage(100)
            _image.Release()

        self.camq_p2read.put("done")

    def _cmd_Release(self, ctx: CamCtx):
        ctx.cam.DeInit()
        ctx.cam = None
        for i in self.idList:
            ctx.cam_list.RemoveBySerial(str(i))
        ctx.cam_list.Clear()
        ctx.system.ReleaseInstance()  # Release instance
        self.camq_p2read.put("done")

    def _cmd_recordPrep(self, ctx: CamCtx) -> None:
        path_base = self.camq.get()
        write_frame_rate = ctx.record_frame_rate
        s_node_map = ctx.cam.GetTLStreamNodeMap()
        handling_mode = PySpin.CEnumerationPtr(s_node_map.GetNode("StreamBufferHandlingMode"))
        if not PySpin.IsAvailable(handling_mode) or not PySpin.IsWritable(handling_mode):
            logger.warning("Unable to set Buffer Handling mode (node retrieval). Aborting...\n")
            return
        handling_mode_entry = handling_mode.GetEntryByName("OldestFirst")
        handling_mode.SetIntValue(handling_mode_entry.GetValue())
        logger.debug(path_base)

        self.height = ctx.aqH
        self.width = ctx.aqW
        self.fps = round(write_frame_rate, 2)

        self.video_file = path_base + ".mp4"
        ctx.file_path = f"{path_base}_timestamps.txt"

        self.async_writer = AsyncFFmpegGPUWriter(
            video_file=self.video_file,
            timestamp_file=ctx.file_path,
            fps=self.fps,
            width=self.width,
            height=self.height,
            max_queue=512,
            qp=23,
        )
        ctx.start_time = 0
        ctx.capture_duration = 0
        ctx.record = True
        self.camq_p2read.put("done")

    def _cmd_Start(self, ctx: CamCtx) -> None:
        cam = ctx.cam
        cam.BeginAcquisition()
        if ctx.ismaster or ctx.isunconnected:
            self.frm.value = 0
            self.camq.get()
            cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)
        while self.aq.value > 0:
            try:
                image_result = cam.GetNextImage(100)  # trying with timeout
            except PySpin.SpinnakerException as e:
                # when doing hardware test, pass value to parent
                # and alert that sync cable error
                logger.error(f"timeout error: {e}")
                # cam.EndAcquisition()
                # cam.DeInit()
                continue

            image_result = ctx.processor.Convert(image_result, PySpin.PixelFormat_BGR8)
            frame_bits = image_result.GetData()
            timestamp = image_result.GetTimeStamp()
            frame_id = image_result.GetFrameID()

            if ctx.record:
                if ctx.start_time == 0:
                    ctx.start_time = timestamp
                    capture_duration = 0
                else:
                    capture_duration = timestamp - ctx.start_time
                    ctx.start_time = timestamp

                # Important: make a real owned NumPy copy before releasing image_result.
                # frame_bgr = cv2.cvtColor(frame_results, cv2.COLOR_RGB2BGR).copy()

                # ok = self.async_writer.write(frame_results, frame_id, capture_duration)
                self.async_writer.write(frame_bits, frame_id, capture_duration)
                # if not ok:
                #     logger.error(f"{self.camID}: async writer queue full; dropped frame {frame_id}")

                # frame_results_rgb = cv2.cvtColor(frame_results, cv2.COLOR_RGB2BGR)

                # test_num+=1
                # self.video_writer.write(frame_results_rgb)
                # if start_time == 0:
                #     start_time = image_result.GetTimeStamp()
                #     time_test = 0
                # else:
                #     time_test = image_result.GetTimeStamp()
                #     capture_duration = time_test- start_time
                #     start_time = time_test #image_result.GetTimeStamp()
                # frame_id = image_result.GetFrameID()
                # # image_result.Save(os.path.join(image_dir,base_name+str(frame_id)+'.bmp'))
                # # avi.Append(image_result)
                # f.write("%s,%s\n" % (frame_id, round(capture_duration)))

            if self.aq.value == 1:
                # Live feed array
                if self.frmGrab.value == 0:
                    frame_results = image_result.GetNDArray().copy()
                    if np.shape(frame_results)[2] == 3:
                        ctx.frameSml[:, :, :] = frame_results[
                            :: self.dwnsmplfac, :: self.dwnsmplfac, :
                        ]
                        self.array4feed[
                            0 : int(ctx.aqH * ctx.aqW * 3 / self.dwnsmplfac / self.dwnsmplfac)
                        ] = ctx.frameSml.flatten()
                    self.frmGrab.value = 1
            image_result.Release()
            if ctx.ismaster:
                self.frm.value += 1

        self.camq.get()
        if ctx.record:
            self.async_writer.close()

            if self.async_writer.dropped_by_writer:
                logger.error(
                    f"{self.camID}: writer dropped {self.async_writer.dropped_by_writer} "
                    f"frames because the queue filled"
                )

            (dropped_frame, total_frames, files_len) = identify_dropped_frames(
                ctx.file_path, self.framerate
            )
            percentage_dropped = int(np.ceil((dropped_frame / total_frames) * 100))
            logger.debug(
                f"{self.camID}: total: {total_frames}, dropped: {dropped_frame}, len: {files_len}"
            )
            # logger.debug(f"{dropped_frame} of camera frames dropped for {self.camID}")
            logger.debug(f"{percentage_dropped}% of camera frames dropped for {self.camID}")

            self.camq_p2read.put(percentage_dropped)
            ctx.record = False

        cam.EndAcquisition()
        cam.TriggerMode.SetValue(PySpin.TriggerMode_On)
        self.frmGrab.value = 0
        if ctx.ismaster:
            cam.LineSelector.SetValue(PySpin.LineSelector_Line1)
            cam.LineSource.SetValue(PySpin.LineSource_FrameTriggerWait)
            cam.LineInverter.SetValue(True)
            cam.LineSelector.SetValue(PySpin.LineSelector_Line1)
            cam.LineSource.SetValue(PySpin.LineSource_Counter0Active)
        self.camq_p2read.put("done")

    def _cmd_Stop(self, ctx: CamCtx) -> None:
        pass  # TODO

    def _cmd_TrigOff(self, ctx: CamCtx) -> None:
        pass  # TODO

    def _cmd_updateSettings(self, ctx: CamCtx) -> None:
        cam = ctx.cam
        cam_cfg = self._rcp_context.user_config.cameras[ctx.camStr]
        nodemap = cam.GetNodeMap()
        binsize = cam_cfg.bin
        # Horizontal Flip
        reverseX = PySpin.CBooleanPtr(nodemap.GetNode("ReverseX"))
        if PySpin.IsAvailable(reverseX) and PySpin.IsWritable(reverseX):
            reverseX.SetValue(cam_cfg.flip)

        # Vertical Flip
        reverseY = PySpin.CBooleanPtr(nodemap.GetNode("ReverseY"))
        if PySpin.IsAvailable(reverseY) and PySpin.IsWritable(reverseY):
            reverseY.SetValue(cam_cfg.flip)

        cam.BinningHorizontal.SetValue(binsize)
        cam.BinningVertical.SetValue(binsize)

        # cam.IspEnable.SetValue(False)
        node_acquisition_mode = PySpin.CEnumerationPtr(nodemap.GetNode("AcquisitionMode"))
        if not PySpin.IsAvailable(node_acquisition_mode) or not PySpin.IsWritable(
            node_acquisition_mode
        ):
            logger.warning(
                "Unable to set acquisition mode to continuous (enum retrieval). Aborting..."
            )
            # todo: previous was returning from main run() method,
            # could maybe continue instead ?
            raise SystemExit(
                "Unable to set acquisition mode to continuous (enum retrieval). Aborting..."
            )
            return False
        # Retrieve entry node from enumeration node
        node_acquisition_mode_continuous = node_acquisition_mode.GetEntryByName("Continuous")
        if not PySpin.IsAvailable(node_acquisition_mode_continuous) or not PySpin.IsReadable(
            node_acquisition_mode_continuous
        ):
            logger.warning(
                "Unable to set acquisition mode to continuous (entry retrieval). Aborting..."
            )
            # todo: previous was returning from main run() method,
            # could maybe continue instead ?
            raise SystemExit(
                "Unable to set acquisition mode to continuous (entry retrieval). Aborting..."
            )
        acquisition_mode_continuous = node_acquisition_mode_continuous.GetValue()
        # Set integer value from entry node as new value of enumeration node
        node_acquisition_mode.SetIntValue(acquisition_mode_continuous)
        # Retrieve the enumeration node from the nodemap
        node_pixel_format = PySpin.CEnumerationPtr(nodemap.GetNode("PixelFormat"))
        if PySpin.IsAvailable(node_pixel_format) and PySpin.IsWritable(node_pixel_format):
            # # Retrieve the desired entry node from the enumeration node
            # node_pixel_format_mono8 = PySpin.CEnumEntryPtr(node_pixel_format.GetEntryByName('Mono8'))
            # if PySpin.IsAvailable(node_pixel_format_mono8) and PySpin.IsReadable(node_pixel_format_mono8):
            #     # Retrieve the integer value from the entry node
            #     pixel_format_mono8 = node_pixel_format_mono8.GetValue()
            #     # Set integer as new value for enumeration node
            #     node_pixel_format.SetIntValue(pixel_format_mono8)
            # else:
            #     logger.warn('Pixel format mono 8 not available...')

            node_pixel_format_BayerRG8 = PySpin.CEnumEntryPtr(
                node_pixel_format.GetEntryByName("BayerRG8")
            )
            if PySpin.IsAvailable(node_pixel_format_BayerRG8) and PySpin.IsReadable(
                node_pixel_format_BayerRG8
            ):
                # Retrieve the integer value from the entry node
                pixel_format_BayerRG8 = node_pixel_format_BayerRG8.GetValue()
                # Set integer as new value for enumeration node
                node_pixel_format.SetIntValue(pixel_format_BayerRG8)
            else:
                logger.debug("Pixel format BayerRG8 not available...")

        else:
            logger.warning("Pixel format not available...")

        # Apply minimum to offset X
        node_offset_x = PySpin.CIntegerPtr(nodemap.GetNode("OffsetX"))
        if PySpin.IsAvailable(node_offset_x) and PySpin.IsWritable(node_offset_x):
            node_offset_x.SetValue(node_offset_x.GetMin())
        else:
            logger.warning("Offset X not available...")
        # Apply minimum to offset Y
        node_offset_y = PySpin.CIntegerPtr(nodemap.GetNode("OffsetY"))
        if PySpin.IsAvailable(node_offset_y) and PySpin.IsWritable(node_offset_y):
            node_offset_y.SetValue(node_offset_y.GetMin())
        else:
            logger.warning("Offset Y not available...")
        # Set maximum width
        node_width = PySpin.CIntegerPtr(nodemap.GetNode("Width"))
        if PySpin.IsAvailable(node_width) and PySpin.IsWritable(node_width):
            width_to_set = node_width.GetMax()
            node_width.SetValue(width_to_set)
        else:
            logger.warning("Width not available...")
        # Set maximum height
        node_height = PySpin.CIntegerPtr(nodemap.GetNode("Height"))
        if PySpin.IsAvailable(node_height) and PySpin.IsWritable(node_height):
            height_to_set = node_height.GetMax()
            node_height.SetValue(height_to_set)
        else:
            logger.warning("Height not available...")
        cam.GainAuto.SetValue(PySpin.GainAuto_Off)
        cam.BalanceWhiteAuto.SetValue(PySpin.BalanceWhiteAuto_Off)

        # Locate the ISP Enable node
        isp_enable_node = PySpin.CBooleanPtr(nodemap.GetNode("IspEnable"))
        if PySpin.IsAvailable(isp_enable_node) and PySpin.IsWritable(isp_enable_node):
            isp_enable_node.SetValue(False)
        else:
            logger.warning("ISP Enable node is not available or read-only.")

        # cam.AdcBitDepth.SetValue(PySpin.AdcBitDepth_Bit8)
        self.camq_p2read.put("done")
        ctx.method = self.camq.get()
        if ctx.method == "crop":
            roi = self.frmdim
            logger.debug(f"roi: {self.frmdim}")
            ctx.record_frame_rate = self.framerate  # int(user_cfg['cam_config']['framerate'])
            # Set width
            node_width = PySpin.CIntegerPtr(nodemap.GetNode("Width"))
            width_max = node_width.GetMax()

            logger.debug(f"node_width:{width_max}")
            width_to_set = np.floor(width_max / roi[3] * cam_cfg.crop[1] / 4) * 4
            if PySpin.IsAvailable(node_width) and PySpin.IsWritable(node_width):
                node_width.SetValue(int(width_to_set))
            else:
                logger.warning("Width not available...")
            # Set height
            node_height = PySpin.CIntegerPtr(nodemap.GetNode("Height"))
            height_max = node_height.GetMax()
            height_to_set = np.floor(height_max / roi[1] * cam_cfg.crop[3] / 4) * 4
            if PySpin.IsAvailable(node_height) and PySpin.IsWritable(node_height):
                node_height.SetValue(int(height_to_set))
            else:
                logger.warning("Height not available...")
            logger.debug(f"node height: {height_max}")
            # Apply offset X
            node_offset_x = PySpin.CIntegerPtr(nodemap.GetNode("OffsetX"))
            offset_x = np.floor(width_max / roi[3] * cam_cfg.crop[0] / 4) * 4
            if PySpin.IsAvailable(node_offset_x) and PySpin.IsWritable(node_offset_x):
                node_offset_x.SetValue(int(offset_x))
            else:
                logger.warning("Offset X not available...")
            # Apply offset Y
            node_offset_y = PySpin.CIntegerPtr(nodemap.GetNode("OffsetY"))
            offset_y = np.floor(height_max / roi[1] * cam_cfg.crop[2] / 4) * 4
            if PySpin.IsAvailable(node_offset_y) and PySpin.IsWritable(node_offset_y):
                node_offset_y.SetValue(int(offset_y))
            else:
                logger.warning("Offset Y not available...")

            ctx.aqW = int(cam_cfg.crop[1] * self.dwnsmplfac)
            ctx.aqH = int(cam_cfg.crop[3] * self.dwnsmplfac)

        else:
            ctx.aqW = int(self.frmdim[3] * self.dwnsmplfac)
            ctx.aqH = int(self.frmdim[1] * self.dwnsmplfac)
            ctx.record_frame_rate = 10

        frame_results = np.zeros([ctx.aqH, ctx.aqW, 3], "ubyte")
        ctx.frameSml = np.zeros(
            [int(ctx.aqH / self.dwnsmplfac), int(ctx.aqW / self.dwnsmplfac), 3], "ubyte"
        )

        cam.AcquisitionFrameRateEnable.SetValue(True)
        cam.Gain.SetValue(cam_cfg.gain)

        # Ensure desired frame rate does not exceed the maximum
        max_frmrate = cam.AcquisitionFrameRate.GetMax()
        ctx.frmrate_time_to_set = min(max_frmrate, ctx.record_frame_rate)
        # cam.AcquisitionFrameRate.SetValue(frmrate_time_to_set)
        if not ctx.ismaster:
            cam.AcquisitionFrameRateEnable.SetValue(False)
        else:
            cam.AcquisitionFrameRate.SetValue(ctx.frmrate_time_to_set)
        exposure_time_to_set = cam.ExposureTime.GetValue()
        logger.info(
            f"max fr: {max_frmrate}, record: {ctx.record_frame_rate}, self.framerate: {self.framerate}"
        )
        logger.info(f"exposure: {exposure_time_to_set}")
        # ctx.record_frame_rate = cam.AcquisitionFrameRate.GetValue()

        cam.AcquisitionFrameRateEnable.SetValue(False)
        if cam.ExposureAuto.GetAccessMode() != PySpin.RW:
            logger.warning("Unable to disable automatic exposure. Aborting...")
            return
        # cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Continuous)
        cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
        if cam.ExposureTime.GetAccessMode() != PySpin.RW:
            logger.warning("Unable to set exposure time. Aborting...")
            return
        # # Ensure desired exposure time does not exceed the maximum
        ctx.max_exposure = cam.ExposureTime.GetMax()
        logger.debug(f"{ctx.camStr} max exposure: {ctx.max_exposure}")
        exposure_time_request = ctx.max_exposure  # int(user_cfg[camStr]['exposure'])
        exposure_time_to_set = floor(1 / ctx.record_frame_rate * 1000 * 1000)
        exposure_time_to_set = min(exposure_time_request, exposure_time_to_set)
        # max_exposure = cam.ExposureTime.GetMax()
        ctx.max_exposure = min(ctx.max_exposure, exposure_time_to_set) * 0.75
        cam.ExposureTime.SetValue(ctx.current_exposure_time)

        cam.AcquisitionFrameRateEnable.SetValue(True)
        cam.Gain.SetValue(cam_cfg.gain)
        cam.Gamma.SetValue(cam_cfg.gamma)
        # Ensure desired frame rate does not exceed the maximum  # gst: this is not ensured. TODO
        max_frmrate = cam.AcquisitionFrameRate.GetMax()
        if not ctx.ismaster:
            cam.AcquisitionFrameRateEnable.SetValue(False)
        else:
            cam.AcquisitionFrameRate.SetValue(ctx.frmrate_time_to_set)
        exposure_time_to_set = cam.ExposureTime.GetValue()
        logger.debug(
            "Spin cam vals: height = %s, width = %s exposure=%s",
            node_height.GetValue(),
            node_width.GetValue(),
            exposure_time_to_set,
        )
        self.camq_p2read.put(node_width.GetValue())
        self.camq_p2read.put(node_height.GetValue())

    def _cmd_setExposure(self, ctx: CamCtx) -> None:
        ctx.cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Continuous)

    def _cmd_getExposure(self, ctx: CamCtx) -> None:
        cam = ctx.cam
        logger.info(f"Current exposure: {ctx.current_exposure_time}")
        ctx.current_exposure_time = cam.ExposureTime.GetValue() * 0.99
        cam.ExposureAuto.SetValue(PySpin.ExposureAuto_Off)
        ctx.current_exposure_time = min(ctx.current_exposure_time, ctx.max_exposure)
        # current_exposure_time = 1.1*max_exposure
        cam.ExposureTime.SetValue(ctx.current_exposure_time)
        logger.debug(f"exposure: {cam.ExposureTime.GetValue()}")
        self.camq_p2read.put(cam.ExposureTime.GetValue())

    def _cmd_setBalance(self, ctx: CamCtx) -> None:
        ctx.cam.BalanceWhiteAuto.SetValue(PySpin.BalanceWhiteAuto_Continuous)

    def _cmd_getBalance(self, ctx: CamCtx) -> None:
        cam = ctx.cam
        cam_cfg = self._rcp_context.user_config.cameras[ctx.camStr]
        cam.BalanceWhiteAuto.SetValue(PySpin.BalanceWhiteAuto_Off)
        cam.Gain.SetValue(cam_cfg.gain)
        cam.Gamma.SetValue(cam_cfg.gamma)
        if not ctx.ismaster:
            cam.AcquisitionFrameRateEnable.SetValue(False)
        else:
            cam.AcquisitionFrameRate.SetValue(ctx.frmrate_time_to_set)
        if ctx.ismaster:
            ctx.record_frame_rate = cam.AcquisitionFrameRate.GetValue()
            self.camq_p2read.put(ctx.record_frame_rate)
        logger.info(f"Frame rate {ctx.camStr}: {self.framerate}")

    def create_primary(self, cam: PySpin.Camera) -> None:
        cam.CounterSelector.SetValue(PySpin.CounterSelector_Counter0)
        cam.CounterEventSource.SetValue(PySpin.CounterEventSource_ExposureStart)
        cam.CounterEventActivation.SetValue(PySpin.CounterEventActivation_RisingEdge)
        cam.CounterTriggerSource.SetValue(PySpin.CounterTriggerSource_ExposureStart)
        cam.CounterTriggerActivation.SetValue(PySpin.CounterTriggerActivation_RisingEdge)
        cam.LineSelector.SetValue(PySpin.LineSelector_Line2)
        cam.V3_3Enable.SetValue(True)
        cam.LineSelector.SetValue(PySpin.LineSelector_Line1)
        cam.LineSource.SetValue(PySpin.LineSource_Counter0Active)
        cam.LineInverter.SetValue(False)
        cam.TriggerMode.SetValue(PySpin.TriggerMode_Off)
        cam.TriggerSource.SetValue(PySpin.TriggerSource_Software)
        cam.TriggerOverlap.SetValue(PySpin.TriggerOverlap_Off)
        cam.TriggerMode.SetValue(PySpin.TriggerMode_On)

    def create_secondary(self, cam: PySpin.Camera, is_decreased: bool) -> None:
        cam.AcquisitionFrameRateEnable.SetValue(False)
        cam.TriggerSource.SetValue(PySpin.TriggerSource_Line3)
        cam.TriggerOverlap.SetValue(PySpin.TriggerOverlap_ReadOut)
        if is_decreased:
            cam.TriggerActivation.SetValue(PySpin.TriggerActivation_RisingEdge)
        else:
            cam.TriggerActivation.SetValue(PySpin.TriggerActivation_AnyEdge)
        cam.TriggerMode.SetValue(PySpin.TriggerMode_On)

    def prepare_writers(self) -> None:
        video_file = self.video_file
        self.video_writer = cv2.VideoWriter(
            video_file,
            cv2.VideoWriter_fourcc("m", "p", "4", "v"),  # type: ignore  # noqa
            self.fps,
            (self.width, self.height),
        )
