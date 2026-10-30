import warnings
from logging import warning
from multiprocessing import sharedctypes
from typing import Any

import numpy as np
import wx
from matplotlib.image import AxesImage

from rcp_task_acquisition.panels.ImagePanel import ImagePanel
from rcp_task_acquisition.utils.camera_settings import CamSettings
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


class TrialPanel(wx.Panel):
    task_trial_item_config: "TaskTrialClassConfig | None" = None

    def __init__(self, parent: wx.Window, *, patient_monitor: int = 0) -> None:
        super().__init__(parent)
        self.seconds = 0
        self.trial_number = 0
        self.countdown_start = 0
        self.button_width = 76
        self.border = 5
        self.trial_is_active = False
        self.instruction_paths: dict[str, str] = {}  # now currently unused

        self.start_video_button: wx.ToggleButton | None = None
        self.pause_video_button: wx.ToggleButton | None = None
        self.video_title: wx.StaticText | None = None

        self.timer: sharedctypes.Synchronized[int]

        vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        vertical_sizer.Add(self._setup_buttons(), 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        self.SetSizer(vertical_sizer)

        self.rest_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.rest_timer)

        # if type(self) is TrialPanel:
        #     self.continue_button.Show()
        # else:
        #     self.continue_button.Hide()

        # for camera views on patient screen:
        self.im: list[AxesImage] = []
        disp = None
        for idx in range(wx.Display.GetCount()):
            if idx == patient_monitor:
                disp = wx.Display(idx)
                break
        if disp is None:
            disp = wx.Display(0)
        logger.debug(
            "display: %s -> %s // %s", disp.GetName(), disp.GetGeometry(), disp.GetClientArea()
        )
        frame = self._frame_patient = wx.Frame(
            parent,
            title="Cameras",
            style=0,
            # style=wx.CLOSE_BOX
            # | wx.CLIP_CHILDREN
            # | wx.FRAME_FLOAT_ON_PARENT,
        )
        disp_size = disp.GetGeometry().GetSize()
        frame_size = wx.Size(int(disp_size.width * 0.8), int(disp_size.height * 0.5))
        # frame.SetSize(frame_size)
        disp_pos = disp.GetGeometry().GetPosition()
        frame.SetPosition(
            wx.Point(
                disp_pos.x + int((disp_size.width - frame_size.width) / 2),
                disp_pos.y + int(frame_size.height * 0.5),
            )
        )
        box_sizer = wx.BoxSizer(wx.VERTICAL)
        panel = self._patient_panel = wx.Panel(frame)
        # panel.SetSize(frame_size)
        box_sizer.Add(panel)
        frame.SetSizer(box_sizer)
        img_panel = self._image_panel = ImagePanel(panel)
        img_panel.SetSize(frame_size)
        img_panel.updateImage()
        panel.Fit()
        frame.Fit()
        frame.Hide()
        logger.debug("frame: pos=%s ; size=%s", frame.GetPosition(), frame.GetSize())
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroyed, self)

    @property
    def patient_frame(self) -> wx.Frame:
        return self._frame_patient

    def _close_patient_win(self):
        logger.debug("_close_patient_win", stacklevel=3)
        self._frame_patient.Hide()
        self._frame_patient.Close()
        self._frame_patient = None

    def _on_destroyed(self, evt: wx.Event):
        self._close_patient_win()

    def on_camera_frame_update(self, index: int, frame: np.ndarray):
        """Allow a panel to intercept camera frame read from shared array, for display purpose"""
        self.im[index].set_data(frame)
        self._image_panel.figure.canvas.draw()

    def update_cams_viewed(self, cams: list[CamSettings]):
        for im, cam in zip(self.im, cams):
            im.set_data(cam.frame)
        self._image_panel.update_names(list(cam.name for cam in cams))

    def prepare_cams(self, cams: list[CamSettings]):
        # logger.debug("received prepare cams: %s", cams)
        # self._frame_patient.Show()
        imp = self._image_panel
        imp.updateImage()
        cam: CamSettings
        for idx, (axe, cam) in enumerate(zip(imp.axes, cams)):
            ims = axe.imshow(cam.frame)
            ims.set_clim(0, 255)
            self.im.append(ims)
            # self.cam_crop.update_crop(idx, axe, cam.frame_dims)
        cam0 = cams[0]
        cam1 = cams[1]
        imp.update_names([cam0.name, cam1.name])
        imp.draw()

    def Close(self, force: bool = False) -> bool:
        ret = self.Unbind(wx.EVT_TIMER, self.rest_timer)
        logger.debug("%s.Close(): unbind timer=%s", self.__class__, ret)
        self._close_patient_win()
        return super().Close(force=force)

    def _setup_buttons(self):
        self.continue_button = wx.ToggleButton(self, label="Begin Trial", size=(150, -1))
        self.continue_button.Hide()
        self.repeat_trial_button = wx.ToggleButton(self, label="Repeat Trial", size=(150, -1))
        self.repeat_trial_button.Hide()
        grid_sizer = wx.GridBagSizer(0, 0)
        grid_sizer.Add(
            self.continue_button,
            pos=(0, 0),
            span=(0, 2),
            flag=wx.ALIGN_LEFT | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            self.repeat_trial_button,
            pos=(1, 0),
            span=(0, 2),
            flag=wx.ALIGN_LEFT | wx.ALL,
            border=self.border,
        )
        return grid_sizer

    def reset(self, count):
        self.seconds = 0

    def show(self):
        logger.verbose("show()")
        self.rest_timer.Start(1000)
        self.Show()

    def hide(self):
        self.rest_timer.Stop()
        self.Hide()

    def start_trial(self):
        self.trial_is_active = True

    def end_trial(self):
        self.trial_is_active = False

    def get_video_buttons(self):
        return self.start_video_button, self.pause_video_button

    def start_video(self):
        self.continue_button.Enable(False)
        self.repeat_trial_button.Enable(False)

    def stop_video(self):
        self.continue_button.Enable(True)
        self.repeat_trial_button.Enable(True)

    def pause_video(self):
        self.continue_button.Enable(True)
        self.repeat_trial_button.Enable(True)

    def resume_video(self):
        self.continue_button.Enable(False)
        self.repeat_trial_button.Enable(False)

    def run_trial(self, count) -> None:
        self.start_trial()

    def get_result(self) -> Any:
        warnings.warn(f"{self.__class__.__name__}.get_result() not implemented", UserWarning)
        return None

    def on_timer(self, event: wx.Event) -> None:
        pass

    def start_new_trial(self) -> None:
        self.trial_number = 0

    def update_values(self) -> None:
        pass

    def add_timer(self, timer: sharedctypes.Synchronized) -> None:
        self.timer = timer

    def populate_metadata(self, metadata: dict):
        """For task metadata. NB: The full global metadata dict is passed."""

    def get_instruction(self, count: int) -> str:
        """Get instruction for play trial. count is trial number"""
        return ""


class TrialPanelWithInstructPlayback(TrialPanel):
    video_title: wx.StaticText
    start_video_button: wx.ToggleButton
    pause_video_button: wx.ToggleButton

    video_buttons: list[wx.ToggleButton]
    other_buttons: list[wx.ToggleButton]

    def setup_instruction_playback(self):
        vid_title = self.video_title = wx.StaticText(self, label="")
        start_but = self.start_video_button = wx.ToggleButton(
            self, label="Play Video", size=(150, -1)
        )
        start_but.Enable(False)
        pause_but = self.pause_video_button = wx.ToggleButton(
            self, label="Pause Video", size=(150, -1)
        )
        pause_but.Enable(False)
        grid_sizer = wx.GridBagSizer(3, 2)
        grid_sizer.Add(
            vid_title,
            pos=(0, 0),
            span=(0, 2),
            flag=wx.ALIGN_LEFT | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            start_but,
            pos=(1, 0),
            span=(0, 1),
            flag=wx.ALIGN_LEFT | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            pause_but,
            pos=(1, 1),
            span=(0, 1),
            flag=wx.ALIGN_LEFT | wx.ALL,
            border=self.border,
        )

        static_box = wx.StaticBox(self, wx.ID_ANY, "Video Instructions")
        static_box_sizer = wx.StaticBoxSizer(static_box, wx.VERTICAL)
        static_box_sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 5)

        return static_box_sizer

    def start_trial(self) -> None:
        super().start_trial()
        self.pause_video_button.Enable(False)
        self.start_video_button.Enable(False)

    def end_trial(self) -> None:
        super().end_trial()
        self.start_video_button.Enable(True)

    def start_video(self) -> None:
        self.start_video_button.SetLabel("Stop Video")
        self.pause_video_button.Enable(True)
        super().start_video()

    def stop_video(self) -> None:
        self.start_video_button.SetLabel("Start Video")
        self.start_video_button.SetValue(False)
        self.pause_video_button.SetValue(False)
        self.pause_video_button.Enable(False)
        super().stop_video()
        self.pause_video_button.SetLabel("Pause Video")

    def pause_video(self):
        self.pause_video_button.SetLabel("Resume Video")
        super().pause_video()

    def resume_video(self):
        self.pause_video_button.SetLabel("Pause Video")
        super().resume_video()


from rcp_task_acquisition.tasks.definitions import TaskTrialClassConfig
# on purpose at the end. prevent import loop cycle.
