import warnings
from logging import warning
from multiprocessing import sharedctypes

import wx

from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


class TrialPanel(wx.Panel):
    def __init__(self, parent: wx.Panel):
        super().__init__(parent)
        self.seconds = 0
        self.trial_number = 0
        self.countdown_start = 0
        self.button_width = 76
        self.border = 5
        self.trial_is_active = False
        self.instruction_paths: str | dict[str, str] = {}
        # str for ToneTaps and FingerTap

        # so there is no error for tasks without videos
        self.start_video_button: wx.ToggleButton | None = None
        self.pause_video_button: wx.ToggleButton | None = None
        self.video_title: wx.StaticText | None = None

        self.timer: sharedctypes.Synchronized[int]

        vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        vertical_sizer.Add(self._setup_buttons(), 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        self.SetSizer(vertical_sizer)

        self.rest_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.rest_timer)

    def populate_metadata(self, metadata: dict):
        """For task metadata. NB: The full global metadata dict is passed."""

    def get_instruction(self, count: int):
        """Get instruction for play trial. count is trial number"""
        warnings.warn(
            f"get_instruction() unexpectedly called on {self.__class__}", UserWarning, stacklevel=3
        )

    def _setup_buttons(self):
        self.continue_button = wx.ToggleButton(self, label="Begin Trial", size=(150, -1))
        self.continue_button.Hide()
        self.repeat_trial = wx.ToggleButton(self, label="Repeat Trial", size=(150, -1))
        self.repeat_trial.Hide()
        grid_sizer = wx.GridBagSizer(0, 0)
        grid_sizer.Add(
            self.continue_button,
            pos=(0, 0),
            span=(0, 2),
            flag=wx.ALIGN_LEFT | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            self.repeat_trial,
            pos=(1, 0),
            span=(0, 2),
            flag=wx.ALIGN_LEFT | wx.ALL,
            border=self.border,
        )
        return grid_sizer

    def reset(self, count):
        self.seconds = 0

    def show(self):
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
        self.repeat_trial.Enable(False)

    def stop_video(self):
        self.continue_button.Enable(True)
        self.repeat_trial.Enable(True)

    def pause_video(self):
        self.continue_button.Enable(True)
        self.repeat_trial.Enable(True)

    def resume_video(self):
        self.continue_button.Enable(False)
        self.repeat_trial.Enable(False)

    def run_trial(self, count) -> None:
        self.start_trial()

    def get_result(self):
        return None

    def on_timer(self, event) -> None:
        pass

    def get_instructions(self):
        return self.instruction_paths

    def start_new_trial(self) -> None:
        self.trial_number = 0

    def update_values(self) -> None:
        pass

    def add_timer(self, timer: sharedctypes.Synchronized) -> None:
        self.timer = timer


class TrialPanelWithInstructPlayback(TrialPanel):
    video_title: wx.StaticText
    start_video_button: wx.ToggleButton
    pause_video_button: wx.ToggleButton

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
