import warnings
from multiprocessing import sharedctypes
from typing import Any

import numpy as np
import wx
from matplotlib.image import AxesImage

from rcp_task_acquisition.panels.ImagePanel import ImagePanel
from rcp_task_acquisition.utils.camera_settings import CamSettings
from rcp_task_acquisition.utils.logger import get_logger

# on purpose at the end. prevent import loop cycle.
from rcp_task_acquisition.tasks.definitions import TaskTrialClassConfig

logger = get_logger(__name__)


class TrialPanel(wx.Panel):
    task_trial_item_config: "TaskTrialClassConfig | None" = None

    button_width = 150
    _continue_button_width: int | None = None

    _main_grid: wx.GridBagSizer | None = None

    @property
    def continue_button_width(self) -> int:
        return self.button_width

    def __init__(self, parent: wx.Window, *, patient_monitor: int = 0) -> None:
        super().__init__(parent)
        self.seconds = 0
        self.trial_number = 0
        self.countdown_start = 0
        self.border = 5
        self.trial_is_active = False
        self.instruction_paths: dict[str, str] = {}  # now currently unused

        self.start_video_button: wx.ToggleButton | None = None
        self.pause_video_button: wx.ToggleButton | None = None
        self.video_title: wx.StaticText | None = None

        self.timer: sharedctypes.Synchronized[int]

        vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        self._buttons_grid = self._setup_buttons()
        vertical_sizer.Add(self._buttons_grid, 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        self.SetSizer(vertical_sizer)

        self.rest_timer = wx.Timer(
            self
        )  # 1s recurrent timer, started/stopped when trial panel is shown/hidden
        self.Bind(wx.EVT_TIMER, self.on_timer, self.rest_timer)

        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroyed, self)

    @staticmethod
    def set_grid_group_enable(grid: wx.GridBagSizer, enabled: bool) -> None:
        for child in grid.Children:
            sub = child.GetWindow()
            if sub is not None:
                sub.Enable(enabled)

    def _on_destroyed(self, evt: wx.Event):
        pass

    def Close(self, force: bool = False) -> bool:
        ret = self.Unbind(wx.EVT_TIMER, self.rest_timer)
        logger.debug("%s.Close(): unbind timer=%s", self.__class__, ret)
        return super().Close(force=force)

    def _setup_buttons(self) -> wx.GridBagSizer:
        self.continue_button = wx.ToggleButton(
            self, label="Begin Trial", size=(self.continue_button_width, -1)
        )
        self.continue_button.Show(type(self) is not TrialPanel)
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

    def reset(self, count: int) -> None:
        """must be extended by subclasses"""
        self.trial_is_active = False
        self.seconds = 0
        self.continue_button.Enable()
        self.continue_button.SetLabel("Begin Trial")
        with wx.EventBlocker(self.continue_button):
            self.continue_button.SetValue(False)

    def show(self) -> None:
        logger.verbose("show()")
        self.rest_timer.Start(1000)
        self.Show()

    def end_task(self) -> None:
        self.hide()

    def hide(self) -> None:
        self.rest_timer.Stop()
        self.Hide()

    def set_trial_running(self, running: bool) -> None:
        """must be extended by subclasses"""
        enabled = not running
        grid = self._main_grid
        if grid is not None:
            self.set_grid_group_enable(grid, enabled)
        self.continue_button.Enable()  # always enabled
        for but in (
            self.repeat_trial_button,
            self.start_video_button,
            self.pause_video_button,
        ):
            if but is not None:
                but.Enable(enabled)

    def start_trial(self) -> None:
        self.trial_is_active = True
        self.seconds = 0
        self.set_trial_running(True)

    def end_trial(self) -> None:
        self.trial_is_active = False
        self.set_trial_running(False)

    def get_video_buttons(self):
        return self.start_video_button, self.pause_video_button

    def start_video(self):
        self.set_begin_trial_enabled(False)

    def stop_video(self) -> None:
        """must be extended by subclasses"""
        self.set_begin_trial_enabled(True)

    def pause_video(self) -> None:
        """must be extended by subclasses"""
        pass

    def resume_video(self) -> None:
        """must be extended by subclasses"""
        pass

    def run_trial(self, count) -> None:
        self.start_trial()

    def get_result(self) -> Any:
        warnings.warn(f"{self.__class__.__name__}.get_result() not implemented", UserWarning)
        return None

    def on_timer(self, event: wx.Event) -> None:
        pass

    def set_begin_trial_enabled(self, enabled: bool = True):
        """can be extended by subclasses"""
        # self.continue_button.Enable(enabled)
        # self.repeat_trial_button.Enable(enabled)
        # with wx.EventBlocker(self.repeat_trial_button):
        #     self.repeat_trial_button.SetValue(False)
        # next_button: wx.ToggleButton | None = getattr(self, "next_button", None)
        # if next_button is not None:
        #     next_button.Enable(enabled)
        grid = self._main_grid
        if grid is not None:
            self.set_grid_group_enable(grid, enabled)

    def start_new_task(self) -> None:
        """Start a new task, i.e not trial execution. must be extended by subclasses"""
        self.trial_number = 0
        self.continue_button.SetLabel("Begin Trial")
        grid = self._main_grid
        if grid is not None:
            self.set_grid_group_enable(grid, False)
            self.continue_button.Enable()

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

    syllable_start_video_button: wx.ToggleButton | None = None
    syllable_pause_video_button: wx.ToggleButton | None = None

    def setup_instruction_playback(self) -> wx.StaticBoxSizer:
        vid_title = self.video_title = wx.StaticText(self, label="")
        start_but = self.start_video_button = wx.ToggleButton(
            self, label="Start Video", size=(150, -1)
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

    def set_begin_trial_enabled(self, enabled: bool = True):
        super().set_begin_trial_enabled(enabled)
        self.get_buttons()
        for group in self.video_buttons, self.other_buttons:
            if len(group) > 1:
                group[0].Enable(enabled)
                group[1].Enable(False)

    def set_trial_running(self, running: bool) -> None:
        super().set_trial_running(running)
        self.get_buttons()
        enabled = not running
        for group in self.video_buttons, self.other_buttons:
            if len(group) > 0:
                group[0].Enable(enabled)

    def start_video(self) -> None:
        super().start_video()
        start, pause = self.get_buttons()
        start.Enable()
        start.SetLabel("Stop Video")
        pause.Enable()

    def stop_video(self) -> None:
        super().stop_video()

        def reset_start_pause(start, pause):
            start.SetLabel("Start Video")
            pause.SetLabel("Pause Video")
            for but in start, pause:
                with wx.EventBlocker(but):
                    but.SetValue(False)
            start.Enable()
            pause.Disable()

        reset_start_pause(*self.get_buttons())
        if len(self.other_buttons) > 1:
            reset_start_pause(self.other_buttons[0], self.other_buttons[1])

    def set_stopped_status(self):
        start, pause = self.get_buttons()
        start.SetLabel("Start Video")
        start.SetValue(False)
        if pause.GetValue():
            pause.SetValue(False)
            pause.SetLabel("Pause Video")
        pause.Enable(False)
        if len(self.other_buttons) > 0:
            self.other_buttons[0].Enable(True)
        self.continue_button.Enable(True)
        # self.next_button.Enable(True)

    def pause_video(self) -> None:
        super().pause_video()
        self.video_buttons[1].SetLabel("Resume Video")

    def resume_video(self) -> None:
        super().resume_video()
        self.video_buttons[1].SetLabel("Pause Video")

    def get_buttons(self) -> tuple[wx.ToggleButton, wx.ToggleButton]:
        syllab_start = self.syllable_start_video_button
        syllab_pause = self.syllable_pause_video_button
        if syllab_start is not None and syllab_start.GetValue():
            assert syllab_pause is not None
            self.video_buttons = [syllab_start, syllab_pause]
            self.other_buttons = [self.start_video_button, self.pause_video_button]
        else:
            self.video_buttons = [self.start_video_button, self.pause_video_button]
            self.other_buttons = (
                [
                    syllab_start,
                    syllab_pause,
                ]
                if syllab_start is not None and syllab_pause is not None
                else []
            )
        return self.video_buttons[0], self.video_buttons[1]

    def set_live_status(self):
        start, pause = self.get_buttons()
        self.continue_button.Enable(False)
        start.SetLabel("Stop Video")
        start.Enable(True)
        pause.Enable(True)
        for but in self.other_buttons:
            but.Enable(False)
