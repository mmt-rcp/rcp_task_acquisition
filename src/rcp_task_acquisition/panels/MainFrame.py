"""
file_utils toolbox
https://github.com/wryanw/file_utils
W Williamson, wallace.williamson@ucdenver.edu

"""

import ctypes
import datetime
import json
import multiprocessing
import os
import shutil
import time
import typing
import warnings
from multiprocessing import Event, Queue, Value
from pathlib import Path
from typing import Any

import wx
import wx.lib.dialogs
import numpy as np
import cv2

from rcp_task_acquisition.models.CameraFrontend import CamerasFrontend
from rcp_task_acquisition.models.Crop import Crop
from rcp_task_acquisition.models.LabjackFrontend import LabjackFrontend
from rcp_task_acquisition.models.SerialDevice import SerialDevice
from rcp_task_acquisition.models.StimulusThread import StimulusMessage, StimulusThread
from rcp_task_acquisition.models.Warnings import WarnCat, WarningHandler
from rcp_task_acquisition.models.participant import Participant, no_participant
from rcp_task_acquisition.panels.ControlsPanel import ControlsPanel
from rcp_task_acquisition.panels.GraphPanel import GraphPanel
from rcp_task_acquisition.panels.ImagePanel import ImagePanel
from rcp_task_acquisition.panels.MetadataPanel import MetadataPanel
from rcp_task_acquisition.panels.TrialPanel import TrialPanel
from rcp_task_acquisition.tasks.Calibration.panel import CalibrationPanel
from rcp_task_acquisition.tasks.Diadochokinesis.panel import DdkPanel
from rcp_task_acquisition.tasks.NaturalisticSpeech.panel import NaturalisticSpeechPanel
from rcp_task_acquisition.tasks.Sara.panel import SaraPanel
from rcp_task_acquisition.tasks.VerbalFluency.panel import VerbalFluencyPanel
from rcp_task_acquisition.tasks.VowelSpace.panel import VowelSpacePanel
from rcp_task_acquisition.tasks.utils import get_task_panel_class
from rcp_task_acquisition.utils import config, file_utils
from rcp_task_acquisition.utils.constants import PLOT_LENGTH, VideoStatus
from rcp_task_acquisition.utils.deidentify_dates import DateDeidentification
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.run_context import RcpRunContext
from rcp_task_acquisition.utils.task_acquisistion_version import __version__
from rcp_task_acquisition.utils.typing import HardwareListsType

logger = get_logger(__name__)


class MainFrame(wx.Frame):
    """Contains the main GUI and button boxes"""

    base_dir: Path  # RawData/participant_id/YYYYMMDD/
    metapath: Path
    sess_dir: Path
    sess_string: str
    session: int
    path_base: str
    date_string: str
    start_time: str = ""
    start_time_utc: str = ""
    is_hidden: bool = False

    trial_panel: TrialPanel

    def __init__(self, parent: wx.Window | None = None, *, rcp_context: RcpRunContext) -> None:
        self._rcp_context = rcp_context
        self.task: str = ""
        self.launch_args: dict[str, Any] = {}
        self.button_pressed = Value(ctypes.c_bool, False)
        self.recording = False
        self.calibrate = False
        self.press_count = Value(ctypes.c_int, 0)
        self.stimulus_timer = Value(ctypes.c_int, 0)
        self.stimulus_panel = Value(ctypes.c_bool, False)
        self.count = 0
        self.frames: float = 0  # ~framerate
        self.results_list: list[Any] = []
        self.serial_device = SerialDevice()
        self.cam_crop = Crop()
        # setting up screen for stimulus thread
        # screen_settings = self.user_cfg["screen_settings"]
        self.labjack_scan_rate: float | None = None
        self.hardware_test = False
        self.exit_stimulus = False
        self.participant = None

        self.warning = WarningHandler()

        # Setting the GUI size and panels design
        displays = tuple(
            wx.Display(i) for i in range(wx.Display.GetCount())
        )  # Gets the number of displays
        screenSizes = [
            display.GetGeometry().GetSize() for display in displays
        ]  # Gets the size of each display
        logger.debug("screenSizes: %s", screenSizes)
        # index = 1 # For display 1.
        if len(screenSizes) != 2:
            self.warning.update_error(WarnCat.DISPLAY).display()
            # sys.exit()
        index = 0
        psychopy_monitor = 1
        if screenSizes[0][0] > screenSizes[1][0]:
            logger.debug("Fist monitor is patient monitor")
            index = 1
            psychopy_monitor = 0
        screenW = screenSizes[index][0]
        self.gui_size = (int(screenW * 0.9), int(screenW * 0.45))
        # self.gui_size = (screenW-90, screenH-55)
        super().__init__(
            parent,
            id=wx.ID_ANY,
            title="Task Master Aquisition",
            size=wx.Size(self.gui_size),
            pos=wx.DefaultPosition,
            style=wx.RESIZE_BORDER | wx.DEFAULT_FRAME_STYLE | wx.TAB_TRAVERSAL,
        )

        self.video_start: wx.ToggleButton | None = None
        self.video_pause: wx.ToggleButton | None = None

        # self.Maximize(True)
        self.statusbar = self.CreateStatusBar()
        self.statusbar.SetStatusText("")
        self.SetSizeHints(
            wx.Size(self.gui_size)
        )  #  This sets the minimum size of the GUI. It can scale now!

        # Spliting the frame into top and bottom panels. Bottom panels contains the widgets. The top panel is for showing images and plotting!
        topSplitter = wx.SplitterWindow(self)
        vSplitter = wx.SplitterWindow(topSplitter)

        self.image_panel = ImagePanel(vSplitter)
        self.image_panel.updateImage()
        self.image_panel.canvas.mpl_connect("button_press_event", self.onClick)

        self.ctrl_panel = GraphPanel(vSplitter, self.gui_size)
        self.widget_panel = ControlsPanel(
            topSplitter, self.ctrl_panel, psychopy_monitor, screenSizes[psychopy_monitor]
        )

        vSplitter.SplitHorizontally(
            self.image_panel, self.ctrl_panel, sashPosition=int(self.gui_size[1] * 0.6)
        )
        topSplitter.SplitVertically(
            vSplitter, self.widget_panel, sashPosition=int(self.gui_size[0] * 0.78)
        )

        topSplitter.SetSashGravity(1)
        vSplitter.SetSashGravity(1)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(topSplitter, 1, wx.EXPAND)
        self.SetSizer(sizer)

        # Add Buttons to the WidgetPanel and bind them to their respective functions.
        (
            self.init,
            self.reset,
            self.update_settings,
            self.play,
            self.rec,
            self.exposure_button,
            self.set_crop,
            self.crop,
            self.minRec,
            self.secRec,
        ) = self.widget_panel.get_cam_handles()

        (
            self.camera_toggle,
            self.hardware_button,
            self.task_button,
            self.quit,
            self.tens_button,
        ) = self.widget_panel.get_task_handles()

        self.contrast_test, self.focus_test, self.hardware_test_panel = (
            self.ctrl_panel.get_hardware_handles()
        )

        self.focus_test.Bind(wx.EVT_TOGGLEBUTTON, lambda _: self.set_focus())
        self.contrast_test.Bind(wx.EVT_TOGGLEBUTTON, lambda _: self.set_contrast())

        self.participant_monitor = self.widget_panel.get_monitor()
        self.cams = CamerasFrontend(
            self.serial_device,
            self.ctrl_panel,
            self.image_panel,
            self.contrast_test,
            self.focus_test,
            self.participant_monitor,
            rcp_context=rcp_context,
        )

        self.trial_panel = self.widget_panel.get_task_panel("")  # to have smth to start with

        self.init.Bind(wx.EVT_TOGGLEBUTTON, lambda _: self.initCams())
        self.update_settings.Bind(wx.EVT_BUTTON, lambda _: self.cams.updateSettings())
        self.play.Bind(wx.EVT_TOGGLEBUTTON, lambda _: self.liveFeed())

        def handle_hardware_test(event: wx.Event):
            self.disable_gui(event)
            toggled = self.hardware_button.GetValue()
            if isinstance(self.trial_panel, CalibrationPanel):
                self._show_patient_cams(toggled)
            else:
                self.widget_panel.show_patient_cams_button.Show(toggled)
                if not toggled:
                    self._show_patient_cams(False)

        self.hardware_button.Bind(wx.EVT_TOGGLEBUTTON, handle_hardware_test)

        self.rec.Bind(wx.EVT_TOGGLEBUTTON, lambda _: self.recordCam())
        self.exposure_button.Bind(wx.EVT_BUTTON, lambda _: self.cams.get_exposure())
        self.task_button.Bind(wx.EVT_TOGGLEBUTTON, self.disable_gui)
        self.tens_button.Bind(wx.EVT_BUTTON, self.tens_pulse)
        self.cam_test = Value(ctypes.c_bool, False)
        self.liveTimer = wx.Timer(self, wx.ID_ANY)
        self.widget_panel.show_patient_cams_button.Bind(
            wx.EVT_TOGGLEBUTTON,
            lambda _: self._show_patient_cams(
                self.widget_panel.show_patient_cams_button.GetValue()
            ),
        )

        # labjack setup
        self.ctrl_panel.create_plot(PLOT_LENGTH)
        self.labjack_stream_button = self.ctrl_panel.get_graph_button()
        self.labjack_choices = self.ctrl_panel.get_graph_choices()

        self.labjack_timer = wx.Timer(self, wx.ID_ANY)
        self.lj = LabjackFrontend(
            PLOT_LENGTH,
            self.ctrl_panel,
            self.labjack_timer,
            self.button_pressed,
            self.press_count,
            self.cam_test,
        )

        self.Bind(wx.EVT_TIMER, self.lj.labjack_event, self.labjack_timer)
        self.labjack_stream_button.Bind(wx.EVT_TOGGLEBUTTON, self.disable_gui)

        # set up cam things
        self.x1 = 0
        self.y1 = 0
        self.frmDims = [0, 1080, 0, 1440]
        self.shared = Value(ctypes.c_byte, 0)
        # self.camaq = Value(ctypes.c_byte, 0)  unused
        # self.frmaq = Value(ctypes.c_int, 0)
        self.frmaq = self.cams.frmaq

        self.dtype = "uint8"
        self.size = self.frmDims[1] * self.frmDims[3] * 3
        self.shape = [self.frmDims[1], self.frmDims[3], 3]

        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyPressed)
        self.Bind(wx.EVT_CHECKBOX, self.update_crop)
        # check the display is correct
        # check the correct monitors are displayed
        # if wx.Display.GetCount() < 2:

        self.video_timer = wx.Timer(self, wx.ID_ANY)
        self.Bind(
            wx.EVT_TIMER, lambda _: self.participant_monitor.update_screen(), self.video_timer
        )
        self.video_timer.Start(500)

        def on_update_cameras_viewed(evt: wx.Event) -> None:
            self.cams.update_cameras_viewed(evt)
            ptr = self.cams.cam_pointer
            cam0, cam1 = self.cams.camera_settings[ptr : ptr + 2]
            self.trial_panel.update_cams_viewed([cam0, cam1])

        self.camera_toggle.Bind(wx.EVT_BUTTON, on_update_cameras_viewed)
        # set up stimulus thread

        self.video_status = Value(ctypes.c_int, 0)

        self.msgq: multiprocessing.Queue[Any] = multiprocessing.Queue()

        self.finish = Value(ctypes.c_byte, 0)
        self.resultsq: Queue[Any] = Queue()
        self.video_lock = Event()
        self.thread = StimulusThread(
            self.msgq,
            self.finish,
            self.shared,
            self.frmaq,
            psychopy_monitor,  # screen_settings,
            self.task,
            self.button_pressed,
            self.press_count,
            self.video_status,
            self.resultsq,
            self.stimulus_timer,
            self.video_lock,
            rcp_context=rcp_context,
        )
        self.startingSession = False
        self.rest_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.update_intertrial, self.rest_timer)
        self.Bind(wx.EVT_TIMER, self.cams.vidPlayer, self.liveTimer)
        self.Bind(wx.EVT_TIMER, self._cams_update, self.liveTimer)
        self.thread.start()
        self.task_active = False
        self.disable_timer = wx.Timer(self, wx.ID_ANY)
        self.Bind(wx.EVT_SIZE, self.on_resize)

    def _show_patient_cams(self, show: bool = True) -> None:
        if show:
            self.msgq.put(StimulusMessage.HIDE_WINDOW)
            self.widget_panel.task_panel.patient_frame.Show()
        else:
            self.msgq.put(StimulusMessage.SHOW_WINDOW)
            self.widget_panel.task_panel.patient_frame.Hide()
        with wx.EventBlocker(self.widget_panel.show_patient_cams_button):
            self.widget_panel.show_patient_cams_button.SetValue(show)

    def _update_task(self, task):
        self.msgq.put(StimulusMessage.UPDATE_TASK)
        self.msgq.put(task)

    def _update_data(self, data):
        self.msgq.put(StimulusMessage.UPDATE_DATA)
        self.msgq.put(data)

    def _cams_update(self, event: wx.Event):
        cams = self.cams
        if cams.camaq.value == 2:
            return
        for cam in cams.cam_dict.values():
            if cam.frmGrab.value == 1:
                cam.frameBuff[0:] = np.frombuffer(cam.array4feed.get_obj(), self.dtype, cam.size)
                dims = cam.frame_size
                frame = cam.frameBuff[0 : dims.dispSize].reshape([dims.h, dims.w, 3])
                frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
                for f in range(3):
                    cam.frame[dims.y1 : dims.y2, dims.x1 : dims.x2, f] = frame[:, :, f]
                cam.frame_size = dims

                self.cams.on_cam_update(cam, cam.frame)
                if cam.idx == cams.cam_pointer:
                    self.trial_panel.on_camera_frame_update(0, cam.frame)
                elif cam.idx == cams.cam_pointer + 1:
                    self.trial_panel.on_camera_frame_update(1, cam.frame)

                cam.frmGrab.value = 0  # only after, when fully consumed,
                # to get eventually a more recent one on next turn.

    @property
    def trial_button(self) -> wx.ToggleButton:
        return self.trial_panel.continue_button

    def on_resize(self, event: wx.Event) -> None:
        wx.CallAfter(self.image_panel.reset_sizing)
        event.Skip()
        # pass

    def run_task(self) -> None:
        logger.verbose("run_task called task_but=%s", self.task_button.GetValue())
        self.Enable()
        if self.task_button.GetValue():
            self.task_active = True
            self.count = 0
            self.finish.value = 0
            is_success = self.lj.start_labjack()
            if not is_success:
                self.task_button.SetValue(False)
                return

            self.labjack_stream_button.SetValue(True)
            self.labjack_stream_button.Enable(False)
            self.labjack_stream_button.SetLabel("Stop Labjack")
            self.prepare_file(self.task, self.participant)
            self.create_file()
            lj_path = os.path.join(self.sess_dir, self.path_base + "_labjack.txt")
            msg = f"P{self.path_base}x"
            self.lj.add_csv(lj_path, self.serial_device, msg)
            self.startingSession = True
            self.task_button.SetLabel("End Task")
            # self.hardware_button.Enable(False)
            if isinstance(self.trial_panel, VowelSpacePanel):
                self.msgq.put(StimulusMessage.VOWEL_SPACE)
                trial_info = self.resultsq.get()
                trial, syllable, finish = trial_info
                self.trial_panel.repeat = True
                self.trial_panel.update_trial(trial, syllable)
            self.trial_panel.start_new_trial()
            self.trial_panel.show()
            # if not self.rest_timer.IsRunning():
            #     self.rest_timer.Start(1000)
        else:
            self.task_active = False
            self.serial_device.write("A")
            time.sleep(3)
            if self.trial_button.GetValue():
                self.trial_button.SetValue(False)
                self.trial_event()
            if self.recording:
                self.cams.stop_recording()
            self.video_status.value = VideoStatus.STOP
            self.task_button.SetLabel("Start Task")
            self.hardware_button.Enable(True)
            self.trial_panel.hide()
            self.msgq.put(StimulusMessage.END_TASK)
            self.labjack_scan_rate = self.lj.stop_labjack()

            self.finish.value = 0
            self.labjack_stream_button.Enable(True)
            if self.labjack_stream_button.GetValue():
                self.labjack_stream_button.SetValue(False)
                self.labjack_stream_button.SetLabel("Stream Labjack")
            self.labjack_stream_button.Enable(True)
            self.end_time = str(f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}Z")
            self.end_time_utc = str(f"{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}Z")
            self.finalize_metadata()
            self.msgq.put(StimulusMessage.RESET_TASK)
            self.labjack_timer.Start(200)
            self.rest_timer.Stop()

    def trial_event(self) -> None:
        """called on initialize or stop of single trial"""
        vid_stat_val = self.video_status.value
        vid_stat: str | VideoStatus
        try:
            vid_stat = VideoStatus(vid_stat_val)
        except ValueError:
            vid_stat = f"Unknown ({vid_stat_val}"
        logger.debug(
            "trial_event(): trial_but=%s video_status=%s", self.trial_button.GetValue(), vid_stat
        )
        if self.trial_button.GetValue():
            logger.debug("in trial button")
            time.sleep(1)
            self.count += 1
            self.cams.trial = self.count
            self.cams.session = self.session
            if vid_stat == VideoStatus.PAUSED:
                self.video_lock.clear()
                self.video_status.value = VideoStatus.STOP
                self.video_lock.wait()
                self.video_lock.clear()
            if vid_stat == VideoStatus.FINISHED:
                logger.debug("ending video")
                self.video_status.value = VideoStatus.NOT_PLAYING
                self.trial_panel.stop_video()

            if not self.rest_timer.IsRunning():
                logger.debug("in trial_event starting rest_timer")
                self.rest_timer.Start(800)
            self.finish.value = 0
            logger.debug("started timer")

            if isinstance(self.trial_panel, VerbalFluencyPanel) and self.trial_panel.first:
                self.count = 0
                self.trial_button.SetLabel("Start Trial")
                self.trial_panel.switch_panel()
                data = self.trial_panel.get_trials()
                self._update_data(data)
                logger.debug("verbal_ fluency first panel")
                return

            try:
                data = self.trial_panel.get_result()
                self._update_data(data)
            except Exception as err:
                logger.exception("Error requesting update data and get result: %s", err)
                self.results_list.append(self.trial_panel.get_result())

            self.trial_panel.run_trial(self.count)
            self.trial_button.SetLabel("Stop Trial")
            self.cams.start_recording(self.base_dir, self.sess_dir, self.path_base, self.count)
            self.liveTimer.Start(150)
            self.msgq.put(StimulusMessage.RUN_TASK)
        else:
            logger.debug("stopping episode")
            self.finish.value = 2

            self.rest_timer.Stop()
            if isinstance(self.trial_panel, SaraPanel):
                self.trial_panel.show_scoring()
            elif isinstance(self.trial_panel, VerbalFluencyPanel):
                self.trial_panel.update_values()
                logger.debug("ending verbal fluency")
            elif isinstance(self.trial_panel, VowelSpacePanel):
                self.trial_panel.repeat_trial_button.Enable(True)
                self.trial_button.SetLabel("Repeat Trial")
                self.trial_panel.repeat_trial_button.SetValue(False)
                self.cams.stop_recording()
                self.liveTimer.Stop()
                # self.rest_timer.Stop()
                self.trial_panel.next_button.Enable(True)
                self.update_task_metadata()
                return
            self.participant_monitor.update_screen()
            self.cams.stop_recording()
            self.trial_button.SetLabel("Begin Trial")
            self.trial_panel.reset(self.count)
            self.trial_panel.end_trial()
            self.liveTimer.Stop()
            self.update_task_metadata()
            logger.debug("ending entire trial")

    def next_trial(self, event: wx.Event) -> None:
        assert isinstance(self.trial_panel, VowelSpacePanel)
        self._update_data(False)
        self.msgq.put(StimulusMessage.VOWEL_SPACE)
        trial_info = self.resultsq.get()
        trial, syllable, finish = trial_info
        self.trial_button.SetLabel("Begin Trial")
        self.trial_panel.update_trial(trial, syllable)
        if finish:
            self.trial_panel.is_finish()

    def repeat_event(self, event: wx.Event) -> None:
        # looks unused
        assert isinstance(self.trial_panel, VowelSpacePanel)
        self.trial_panel.repeat_event()
        self.trial_event()

    def update_intertrial(self, event: wx.Event) -> None:
        logger.debug(
            "update_intertrial: finish=%s, video=%s", self.finish.value, self.video_status.value
        )
        if self.video_status.value == VideoStatus.FINISHED:
            logger.debug("in finish")
            self.trial_panel.stop_video()
            self.video_status.value = VideoStatus.NOT_PLAYING
            logger.debug("called stop_video")
            self.rest_timer.Stop()
        elif self.video_status.value == VideoStatus.ERROR:
            self.trial_panel.stop_video()
            self.video_status.value = VideoStatus.NOT_PLAYING
            self.warning.update_error(WarnCat.VIDEO).display()
        elif self.finish.value == 1 and not isinstance(
            self.widget_panel.task_panel, (NaturalisticSpeechPanel, VowelSpacePanel)
        ):
            # logger.debug("in intertrial")
            self.participant_monitor.update_screen()
            self.cams.stop_recording()
            self.trial_panel.reset(self.count)
            self.trial_panel.end_trial()
            self.stimulus_panel.value = False
            self.liveTimer.Stop()
            self.finish.value = 0
            self.trial_panel.update_values()
            self.trial_button.SetLabel("Start Trial")
            self.rest_timer.Stop()
            self.update_task_metadata()

    def play_instructions(self, event: wx.Event) -> None:
        geo = event.GetEventObject()
        assert isinstance(geo, wx.ToggleButton)
        if geo.GetValue():
            result = self.trial_panel.get_instruction(self.count)
            logger.debug("putting PLAY_INSTRUCTIONS %r to process", result)
            # self.thread.play_video()
            self.msgq.put(StimulusMessage.PLAY_INSTRUCTIONS)
            self.msgq.put(result)
            self.video_status.value = VideoStatus.PLAY
            self.trial_panel.start_video()
            if not self.rest_timer.IsRunning():
                self.rest_timer.Start(800)
        else:
            logger.debug("stopping_video")
            self.video_status.value = VideoStatus.STOP
            self.trial_panel.stop_video()
            self.rest_timer.Stop()
            logger.debug("done stopping: %s", self.video_status.value)

    def pause_instructions(self, event: wx.Event) -> None:
        geo = event.GetEventObject()
        assert isinstance(geo, wx.ToggleButton)
        if geo.GetValue():
            self.video_status.value = VideoStatus.PAUSED
            self.trial_panel.pause_video()
        else:
            self.video_status.value = VideoStatus.START_FROM_PAUSE
            self.trial_panel.resume_video()

    def set_focus(self) -> None:
        if self.focus_test.GetValue():
            self.contrast_test.Enable(False)
            self.cam_test.value = True
            self.cams.update_focus()
            self.ctrl_panel.setup_test_legend()
        else:
            self.ctrl_panel.remove_hardware()
            self.contrast_test.Enable(True)
            self.cams.update_focus(False)
            self.cam_test.value = False

    def set_contrast(self) -> None:
        if self.contrast_test.GetValue():
            self.focus_test.Enable(False)
            self.cam_test.value = True
            self.ctrl_panel.setup_test_legend()
            self.cams.update_contrast()
        else:
            self.ctrl_panel.remove_hardware()
            self.focus_test.Enable(True)
            self.cams.update_contrast(False)
            self.cam_test.value = False

    def liveFeed(self) -> None:
        button_label = self.play.GetLabel()
        if button_label == "Abort":
            self.rec.SetValue(False)
            self.recordCam()
            if wx.MessageBox(
                "Are you sure?", caption="Abort", style=wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION
            ):
                shutil.rmtree(self.sess_dir)
                time.sleep(5)
            self.play.SetValue(False)
            self.shared.value = -1
        elif self.play.GetValue() == True or button_label == "Hardware Test":
            if button_label == "Hardware Test":
                self.Enable()
                self.hardware_test = True
                self.hardware_test_panel.Show()
                if self.task_active:
                    is_success = True
                else:
                    is_success = self.lj.start_labjack()
                self.msgq.put(StimulusMessage.HARDWARE_TEST)
                if not is_success:
                    logger.error("Error loading labjack_stream")
                else:
                    self.labjack_stream_button.SetValue(True)
                    self.labjack_stream_button.Enable(False)
                    self.labjack_stream_button.SetLabel("Stop Labjack")
            if not self.liveTimer.IsRunning():
                self.cams.live_start()
                self.liveTimer.Start(150)
                self.play.SetLabel("Stop")
                self.hardware_button.SetLabel("End Test")
            self.set_crop.Enable(False)
            self.rec.Enable(False)
            self.minRec.Enable(False)
            self.secRec.Enable(False)
            self.update_settings.Enable(False)

        else:
            self.shared.value = -1
            if self.liveTimer.IsRunning():
                self.liveTimer.Stop()
            self.cams.live_stop()
            self.play.SetLabel("Live")
            self.hardware_button.SetLabel("Hardware Test")
            if self.hardware_test:
                self.cam_test.value = False
                self.hardware_test = False
                self.focus_test.Enable(True)
                self.focus_test.SetValue(False)
                self.contrast_test.SetValue(False)
                self.contrast_test.Enable(True)
                self.set_focus()
                self.set_contrast()
                self.finish.value = 2
                self.hardware_test_panel.Hide()
                self.hardware_test = False
                if self.task_active:
                    self.labjack_scan_rate = self.lj.stop_labjack()
                    self.labjack_stream_button.Enable(True)
                    if self.labjack_stream_button.GetValue():
                        self.labjack_stream_button.SetValue(False)
                        self.labjack_stream_button.SetLabel("Stream Labjack")
                    self.labjack_stream_button.Enable(True)
            buttons = [self.set_crop, self.rec, self.minRec, self.secRec, self.update_settings]
            self.enable_group(buttons, False)

    def hardwareFeed(self, event: wx.Event) -> None:
        # clicked_button = event.GetEventObject()
        # button_label = clicked_button.GetLabel()
        self.Enable()
        if self.hardware_button.GetValue():
            self.hardware_test = True
            self.hardware_test_panel.Show()
            self.msgq.put(StimulusMessage.HARDWARE_TEST)
            if not self.task_active:
                is_success = self.lj.start_labjack()

                if not is_success:
                    logger.error("Error loading labjack_stream")
                else:
                    self.labjack_stream_button.SetValue(True)
                    self.labjack_stream_button.Enable(False)
                    self.labjack_stream_button.SetLabel("Stop Labjack")
            if not self.liveTimer.IsRunning():
                self.cams.live_start()
                self.liveTimer.Start(150)
                self.play.SetLabel("Stop")
                self.hardware_button.SetLabel("End Test")
            self.set_crop.Enable(False)
            self.rec.Enable(False)
            self.minRec.Enable(False)
            self.secRec.Enable(False)
            self.update_settings.Enable(False)
            self.task_button.Enable(False)
        else:
            self.shared.value = -1
            if self.liveTimer.IsRunning():
                self.liveTimer.Stop()
            self.cams.live_stop()
            self.play.SetLabel("Live")
            self.hardware_button.SetLabel("Hardware Test")
            if self.hardware_test:
                self.cam_test.value = False
                self.hardware_test = False
                self.focus_test.Enable(True)
                self.focus_test.SetValue(False)
                self.contrast_test.SetValue(False)
                self.contrast_test.Enable(True)
                self.set_focus()
                self.set_contrast()
                self.finish.value = 2
                self.hardware_test_panel.Hide()
                self.hardware_test = False
                if not self.task_active:
                    self.labjack_scan_rate = self.lj.stop_labjack()
                    self.labjack_stream_button.Enable(True)
                    if self.labjack_stream_button.GetValue():
                        self.labjack_stream_button.SetValue(False)
                        self.labjack_stream_button.SetLabel("Stream Labjack")
                        self.labjack_stream_button.Enable(True)
            self.set_crop.Enable(True)
            self.rec.Enable(True)
            self.minRec.Enable(True)
            self.secRec.Enable(True)
            self.update_settings.Enable(True)
            self.task_button.Enable(True)

    def create_metadata(self) -> None:
        logger.verbose("create_metadata called")
        meta = file_utils.metadata_template()
        self._update_metadata(meta)

    def update_metadata(self):
        meta = file_utils.read_metadata(self.metapath)
        self._update_metadata(meta)

    def _update_metadata(self, meta: dict) -> None:
        user_cfg = self._rcp_context.user_config
        # self.meta['screen_settings'] = self.user_cfg['screen_settings']
        # meta_name = f"{self.path_base}_metadata.yaml"
        # self.metapath = Path(self.sess_dir, meta_name)
        cameras_meta = {}
        meta["version"] = str(__version__)
        meta["actual_scan_rate"] = self.labjack_scan_rate

        for cam_d in self.cams.cam_dict.values():
            cfg = user_cfg.cameras[cam_d.name]
            cameras_meta[cam_d.name] = {
                "serial": cfg.serial,
                "ismaster": cfg.ismaster,
                "crop": cfg.crop,
                "bin": cfg.bin,
                "nickname": cam_d.name,
                "actual_framerate": cam_d.actual_framerate,
                "actual_exposure": cam_d.exposure,
            }
        meta["cameras"] = config.to_raw_recursive(cameras_meta)
        meta["unitRef"] = user_cfg.unitRef
        meta["Collection"] = "info"
        meta["hardware"] = config.to_raw_recursive(user_cfg.hardware)

        meta["StartTime_Local"] = self.start_time
        meta["StartTime_UTC"] = self.start_time_utc
        meta["administrator_id"] = self.launch_args["administrator_id"]
        meta["participant_id"] = self.launch_args["participant_id"]
        meta["participant_details"] = self.launch_args["participant_detail"]

        meta["task"] = self.task
        meta["task_settings"] = self._rcp_context.tasks_config[self.task].settings

        # if self.task == "verbal_fluency":
        #     self.meta["trial_data"]["categories"] = self.trial_panel.add_metadata()
        # if self.task == "sara":
        #     self.meta["trial_data"] = self.trial_panel.add_metadata()

        file_utils.write_metadata(meta, self.metapath)

    def finalize_metadata(self) -> None:
        logger.verbose("finalize_metadata called")
        metadata_panel = MetadataPanel()
        user_cfg = self._rcp_context.user_config
        res = metadata_panel.show()
        metadata_panel.dialog.Close()
        if res == wx.ID_OK:
            metadata = file_utils.read_metadata(self.metapath)
            logger.debug("read metadata: %s", metadata)
            metadata["actual_scan_rate"] = self.labjack_scan_rate
            for key, value in metadata_panel.metadata.items():
                metadata[key] = value
            metadata["EndTime_Local"] = self.end_time
            metadata["EndTime_UTC"] = self.end_time_utc
            if isinstance(self.trial_panel, SaraPanel):
                metadata["trial_data"] = self.trial_panel.add_metadata()

            file_utils.write_metadata(metadata, self.metapath)

            deidentify = DateDeidentification(user_cfg)
            deidentify.deidentify_one_session(self.sess_dir, self.date_string)
        else:
            # remove entire directory
            logger.verbose("removing session dir %s", self.sess_dir)
            shutil.rmtree(self.sess_dir, ignore_errors=True)

    def update_task_metadata(self) -> None:
        self.msgq.put(StimulusMessage.SEND_METADATA)
        try:
            trial_data = json.loads(self.resultsq.get())
        except Exception as err:
            logger.error("update task metadata error: %s", err)
            trial_data = None
        metadata = file_utils.read_metadata(self.metapath)
        logger.debug("%s yaml loaded sections: %r", self.metapath, tuple(metadata))
        metadata["trial_data"] = trial_data
        self.trial_panel.populate_metadata(metadata)
        file_utils.write_metadata(metadata, self.metapath)

    def prepare_file(self, task: str, participant: Participant | None) -> None:
        logger.verbose("prepare_file called")
        part = participant
        if part is None:
            logger.verbose("setting no_participant for create_file")
            part = no_participant
            # what todo ?
        task_panel_cls = get_task_panel_class(self.task)
        task_item_cfg = task_panel_cls.task_trial_item_config
        if task_item_cfg is None:
            code_path_part = task
            if not issubclass(task_panel_cls, CalibrationPanel):
                logger.warning("unexpected task with None task_trial_item_config: %s", task)
        else:
            code_path_part = task_item_cfg.path_part
        ctx = self._rcp_context
        user_cfg = ctx.user_config
        unit_ref = user_cfg.unitRef
        date_string = datetime.datetime.now(tz=datetime.timezone.utc).strftime("%Y%m%d")
        self.date_string = date_string

        if issubclass(task_panel_cls, CalibrationPanel):
            calibrate_path = Path(user_cfg.RawDataDir).parent
            base_dir = self.base_dir = Path(calibrate_path, "CalibrationData", date_string)
            prev_expt_list = [p for p in base_dir.glob("*")]
            file_count = len(prev_expt_list) + 1
            self.session = file_count
            self.sess_string = "%s_%03d" % (self.task, file_count)
            self.sess_dir = Path(self.base_dir, self.sess_string)
            if not self.sess_dir.exists():
                self.sess_dir.mkdir(parents=True, exist_ok=True)
            self.date_string = datetime.datetime.utcnow().strftime("%Y%m%d")
            self.path_base = f"{self.date_string}_{user_cfg.unitRef}_{self.sess_string}"
            meta_name = f"{self.path_base}_metadata.yaml"
            self.metapath = Path(self.sess_dir, meta_name)
        else:
            base_dir = self.base_dir = Path(ctx.user_config.RawDataDir, part.id, date_string)
            prev_expt_list = (
                [v for v in base_dir.glob("*") if v.is_dir()] if base_dir.exists() else []
            )
            file_count = len(prev_expt_list) + 1
            self.session = file_count
            self.sess_string = f"{code_path_part}{file_count:03d}"
            self.sess_dir = Path(base_dir, self.sess_string)
            self.path_base = f"{part.id}_{date_string}_{self.sess_string}_{unit_ref}"
            meta_name = f"{self.path_base}_metadata.yaml"
            self.metapath = Path(self.sess_dir, meta_name)
        logger.notice("prepared new metapath: %s", self.metapath)

    def create_file(self) -> None:
        if not self.sess_dir.exists():
            self.sess_dir.mkdir(parents=True, exist_ok=True)
        self.create_metadata()

    def initCams(self) -> bool:  # NB: but return value unused/unchecked in all callers
        logger.verbose("initCams()")
        # self.trial_panel.Show()
        if self.init.GetValue():
            success = self.cams.initialize()
            if not success:
                logger.error("cams initialize failed")
                return False
            self.trial_panel.prepare_cams(self.cams.camera_settings[:2])
            self.init.SetLabel("Release")
            self.exposure_button.Enable(True)
            self.play.Enable(True)
            self.rec.Enable(True)
            self.minRec.Enable(True)
            self.secRec.Enable(True)
            self.update_settings.Enable(True)
            self.crop.Enable(False)
            self.reset.Enable(False)
            self.Enable(True)

            self.task_button.Enable(True)
            self.image_panel.draw()
        else:
            self.init.SetLabel("Enable")
            self.cams.deinitialize()
            # if self.serSuccess:
            #     self.ser.close()
            if self.rec.GetValue():
                self.rec.SetValue(False)
                self.recordCam()
            if self.play.GetValue():
                self.play.SetValue(False)
                self.liveFeed()
            if self.set_crop.GetValue():
                self.set_crop.SetValue(False)

            self.image_panel.draw()
            self.set_crop.Enable(False)
            self.play.Enable(False)
            self.rec.Enable(False)
            self.minRec.Enable(False)
            self.secRec.Enable(False)
            self.crop.Enable(True)
            self.reset.Enable(True)
            self.update_settings.Enable(False)
            # self.cams.deinitThreads()
        return True

    def tens_pulse(self, event: wx.Event) -> None:
        self.serial_device.write("A")

    def quitButton(self) -> None:
        """
        Quits the GUI
        """
        logger.info("Close event called")
        self.statusbar.SetStatusText("closing..")
        if self.thread.is_alive():
            try:
                self.msgq.put(StimulusMessage.CLOSE_WINDOW)
                self.thread.join(2)
                if self.thread.is_alive():
                    logger.warning("Stimulus still active after close")
                    self.thread.terminate()
                    self.thread.join(1)
            except Exception as err:
                logger.error("Error request close_window to stimulus: %s", err)
        else:
            logger.debug("Stimulus not alive")

        try:
            self.widget_panel.Close(True)
        except Exception as err:
            logger.debug("error close task panel: %s", err, exc_info=True)
        self.ctrl_panel.Close(True)
        self.statusbar.SetStatusText("")
        self.Close()

    def Hide(self) -> bool:
        self.is_hidden = True
        self.lj.stop_labjack()
        self.video_timer.Stop()
        self.rest_timer.Stop()
        self.video_status.value = VideoStatus.STOP
        if self.recording:
            self.cams.stop_recording()
        if self.play.GetValue():
            self.play.SetValue(False)
            self.liveFeed()
        if self.rec.GetValue():
            self.rec.SetValue(False)
            self.recordCam()
        # If running a task
        if self.hardware_button.GetValue():
            self.hardware_button.SetValue(False)
            self.liveFeed()
        if self.task_button.GetValue():
            self.task_button.SetValue(False)
            self.run_task()
        if self.init.GetValue():
            self.init.SetValue(False)
            self.initCams()
        self.trial_panel.Hide()
        return super().Hide()

    def update_crop(self, event):
        value = bool(self.crop.GetValue())
        self.cams.update_crop(value)

    def recordCam(self) -> None:
        is_rec = self.rec.GetValue()
        is_task = self.task_button.GetValue()
        logger.verbose("recordCam(): rec=%s task_button=%s", is_rec, is_task)
        if is_rec or is_task:
            if self.recording:
                return
            self.recording = True
            if self.calibrate:
                self.task_button.SetLabel("Stop Recording")
                self.trial_panel.reset(0)
                self.trial_panel.show()
                self.prepare_file(self.task, self.participant)
            # else:
            #     self.create_file()

            self.cams.start_recording(self.base_dir, self.sess_dir, self.path_base, self.count)
            self.set_crop.Enable(False)
            self.minRec.Enable(False)
            self.secRec.Enable(False)
            self.exposure_button.Enable(False)
            self.update_settings.Enable(False)
            self.rec.SetLabel("Stop")
            self.play.SetLabel("Abort")
            self.liveTimer.Start(150)
        else:
            if not self.recording:
                return
            self.recording = False
            self.cams.stop_recording()
            self.rec.SetLabel("Record")
            self.play.SetLabel("Live")
            self.liveTimer.Stop()
            self.set_crop.Enable(True)
            self.minRec.Enable(True)
            self.exposure_button.Enable(True)
            self.secRec.Enable(True)
            self.update_settings.Enable(True)
            if self.calibrate:
                self.task_button.SetLabel("Record Cameras")
                self.trial_panel.rest_timer.Stop()
                # self.trial_panel.hide()  # this also cancel the task/trial 1s timer
                if "face" not in self.task:
                    for p in self.sess_dir.glob("*"):
                        if "Face" in p.name:
                            logger.debug("removing %s", p)
                            p.unlink(missing_ok=True)
                # remove any files that arent the calibraated files

    def onClick(self, event: wx.Event) -> None:
        if self.set_crop.GetValue():
            cameras = self._rcp_context.user_config.cameras
            self.cam_crop.adjust_crop(
                event, self.image_panel.axes, [cam_item.value for cam_item in cameras], cameras
            )
            self.cam_crop.drawROI(self.image_panel.axes)
            self.image_panel.figure.canvas.draw()

    def OnKeyPressed(self, event: wx.Event) -> None:
        keyCode = event.GetKeyCode()
        # Save the new ROI parameters
        if keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            pass
            # Write the new parameters to the user config file
            # TODO: dead: refering to attributes never assigned
            # if self.set_crop.GetValue():
            #     self.cam_crop.create_crop(self.cam_config, self.camStrList, self.cam_config)
            # file_utils.write_config(self.user_cfg)
            # self.set_crop.SetValue(False)
            # self.widget_panel.Enable(True)
            # self.play.SetFocus()
        # Modify existing ROI parameters
        elif self.set_crop.GetValue() == True and keyCode in (
            wx.WXK_UP,
            wx.WXK_DOWN,
            wx.WXK_LEFT,
            wx.WXK_RIGHT,
            ord("A"),
            ord("S"),
            wx.WXK_DELETE,
        ):
            self.cam_crop.set_key_crop(self.image_panel.axes, keyCode)
            self.cam_crop.drawROI(self.image_panel.axes)
            self.image_panel.figure.canvas.draw()
        # Any other case
        else:
            event.Skip()

    def init_and_show(self, launch_args: dict[str, Any]) -> None:
        logger.verbose("show(): launch_args=%s", launch_args)
        self.start_time = str(f"{datetime.datetime.now().strftime('%Y%m%d%H%M%S')}Z")
        self.start_time_utc = str(f"{datetime.datetime.utcnow().strftime('%Y%m%d%H%M%S')}Z")
        self.labjack_scan_rate = None
        self.cams.reset_variables()
        self.hardware_test = False
        self.cam_test.value = False
        self.launch_args = launch_args
        task = self.task = launch_args["task"].strip()
        self.participant = launch_args["participant"]
        self._update_task(task)
        self.video_status.value = VideoStatus.NOT_PLAYING
        tasks_cfg = self._rcp_context.tasks_config
        user_cfg = self._rcp_context.user_config
        cams_cfg = user_cfg.cameras
        args: config.HardwareDictConfig
        if not self.task or self.task not in tasks_cfg:
            logger.debug("task %r not in tasks_cfg (%s)", self.task, tuple(tasks_cfg))
            args = user_cfg.hardware
            self.widget_panel.show_cams()
            self.frames = user_cfg.cam_config.framerate
        else:
            logger.debug("populating cameras and hardware configs")
            cams_cfg = config.CamerasDictConfig()
            args = config.HardwareDictConfig()
            self.frames = 0
            task_cfg = tasks_cfg[self.task]
            self.widget_panel.hide_cams()
            for hard_name in task_cfg.settings:
                if hard_name in user_cfg.hardware:
                    args[hard_name] = user_cfg.hardware[hard_name]
                elif hard_name in user_cfg.cameras:
                    cams_cfg[hard_name] = user_cfg.cameras[hard_name]
                else:
                    logger.warning(
                        "Task %s: unknown hardware name in task settings: %s", task, hard_name
                    )
        # logger.debug(f"args: {args}")
        hard_gen = ((arg.value, v.labjack_input, "", v.voltage_range) for arg, v in args.items())
        sorted_hardware: tuple[tuple[str, str, str, tuple[float, float]], ...] = tuple(
            sorted(hard_gen, key=lambda item: item[1])
        )
        hardware_lists: HardwareListsType = typing.cast(
            HardwareListsType, tuple(zip(*sorted_hardware))
        )
        # logger.debug(hardware_lists)
        self.cams.setup(cams_cfg, user_cfg.cam_config.is_unconnected, self.frames)
        self.init.SetValue(True)
        self.widget_panel.update_task(task)
        self.trial_panel: TrialPanel = self.widget_panel.get_trial_panel()
        self.trial_panel.continue_button.Bind(wx.EVT_TOGGLEBUTTON, lambda _: self.trial_event())
        self.trial_panel.repeat_trial_button.Bind(wx.EVT_TOGGLEBUTTON, lambda _: self.trial_event())
        self.initCams()
        self.lj.update_hardware(hardware_lists)
        self.press_count.value = 0
        self.video_start, self.video_pause = self.trial_panel.get_video_buttons()
        if isinstance(self.trial_panel, CalibrationPanel):
            self.calibrate = True
            self.task_button.Bind(wx.EVT_TOGGLEBUTTON, lambda _: self.recordCam())
            self.task_button.SetLabel("Record Cameras")
        else:
            self.calibrate = False
            self.task_button.Bind(wx.EVT_TOGGLEBUTTON, lambda _: self.run_task())
            self.task_button.SetLabel("Start Task")
        if self.task == "all_hardware":
            self.task_button.Enable(False)
        else:
            self.task_button.Enable(True)
        if self.video_start is not None:
            self.video_start.Bind(wx.EVT_TOGGLEBUTTON, self.play_instructions)
            self.video_pause.Bind(wx.EVT_TOGGLEBUTTON, self.pause_instructions)
            if isinstance(self.trial_panel, (DdkPanel, VowelSpacePanel)):
                self.trial_panel.syllable_start_video_button.Bind(
                    wx.EVT_TOGGLEBUTTON, self.play_instructions
                )
                self.trial_panel.syllable_pause_video_button.Bind(
                    wx.EVT_TOGGLEBUTTON, self.pause_instructions
                )
            if isinstance(self.trial_panel, VowelSpacePanel):
                self.trial_panel.next_button.Bind(wx.EVT_BUTTON, self.next_trial)
        self.participant_monitor.update_screen()
        self.trial_panel.add_timer(self.stimulus_timer)
        self.msgq.put(StimulusMessage.INITIALIZE)
        self.Show()  # NB: we are in the method `def show(...)` : lower-case s

    def Show(self, show: bool = True) -> bool:
        if show:
            self.video_timer.Start(500)
        return super().Show(show)

    def disable_gui(self, event: wx.Event) -> None:
        handle = event.GetEventObject()
        if handle == self.task_button:
            self.Bind(wx.EVT_TIMER, lambda _: self.run_task(), self.disable_timer)
        if handle == self.hardware_button:
            self.Bind(wx.EVT_TIMER, self.hardwareFeed, self.disable_timer)
        if handle == self.labjack_stream_button:
            self.Bind(wx.EVT_TIMER, self.labjack_stream, self.disable_timer)
        self.Disable()
        self.disable_timer.StartOnce(80)

    def labjack_stream(self, event: wx.Event) -> None:
        self.lj.labjack_stream(event)
        self.Enable()

    def enable_group(self, buttons: list[wx.ToggleButton], value: bool):
        for button in buttons:
            button.Enable(value)
