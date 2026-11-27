import json
from typing import Any

import wx

from rcp_task_acquisition.panels.TrialPanel import TrialPanel, TrialPanelWithInstructPlayback
from rcp_task_acquisition.tasks.VerbalFluency.VerbalFluency import VerbalFluency
from rcp_task_acquisition.tasks.VerbalFluency.constants import (
    PHONEMIC_LIST,
    PHONEMIC_PHRASE,
    SEMANTIC_LIST,
    SEMANTIC_PHRASE,
    TRIAL_TIME,
)
from rcp_task_acquisition.tasks.definitions import TaskTrialClassConfig
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


class VerbalFluencyPanel(TrialPanelWithInstructPlayback):
    task_trial_item_config = TaskTrialClassConfig(
        "verbal_fluency", "Verbal Fluency", "verbalfluency", VerbalFluency
    )
    _main_grid: wx.GridBagSizer

    def __init__(self, *args, **kwargs) -> None:
        super().__init__(*args, **kwargs)
        self.prompt = None
        self.type = None
        self.first = True
        self.value: str = ""
        self.trial_num = 0
        self.actual_list: list[str] = []
        self.phonemic_list: list[str] = []  # list of 1 char strings
        self.initial_list = PHONEMIC_LIST
        self.semantic: str = ""
        self.trial_is_active = False

        vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        grid = self._main_grid = self._setup_panel()
        vertical_sizer.Add(grid, 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        self._video_instruction_grid = self.setup_instruction_playback()
        vertical_sizer.Add(self._video_instruction_grid, 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        self.SetSizer(vertical_sizer)

    def populate_metadata(self, metadata: dict):
        metadata["trial_data"]["categories"] = self.add_metadata()

    def _set_phonemic_task(self) -> None:
        self.phonemic_list = json.loads(self.initial_list[self.phonemic_choice.GetSelection()])
        self.semantic = self.semantic_list[self.semantic_choice.GetSelection()]
        if self.trial_num > len(self.phonemic_list) - 1:
            return
        self.value = self.phonemic_list[self.trial_num]
        self.prompt_text.SetLabel(PHONEMIC_PHRASE.replace("*", self.value))
        self.prompt_text.Wrap(299)
        self.video_title.SetLabel(f"Trial: {self.value}")
        self.start_video_button.Enable()

    def _setup_panel(self) -> wx.GridBagSizer:
        self.phonemic_task = wx.StaticText(self, label="Choose Phonemic Category:")
        choice = self.phonemic_choice = wx.Choice(
            self, id=wx.ID_ANY, choices=self.initial_list, size=(200, -1)
        )
        choice.Bind(wx.EVT_CHOICE, lambda _: self._set_phonemic_task())

        self.semantic_task = wx.StaticText(self, label="Choose Semantic Category:")
        self.semantic_list = SEMANTIC_LIST
        self.semantic_choice = wx.Choice(
            self, id=wx.ID_ANY, choices=self.semantic_list, size=(200, -1)
        )

        self.prompt_text = wx.StaticText(self, label="", size=(300, 50))
        self.seconds_text = wx.StaticText(self, label="", size=(300, -1))

        grid_sizer = wx.GridBagSizer(7, 6)
        grid_sizer.Add(
            self.phonemic_task,
            pos=(0, 0),
            span=(0, 2),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            self.phonemic_choice,
            pos=(1, 0),
            span=(0, 4),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            self.semantic_task,
            pos=(2, 0),
            span=(0, 2),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            self.semantic_choice,
            pos=(3, 0),
            span=(0, 4),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            self.seconds_text,
            pos=(4, 0),
            span=(0, 4),
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            self.prompt_text,
            pos=(5, 0),
            span=(0, 5),
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=self.border,
        )
        self._buttons_grid.Detach(self.continue_button)
        grid_sizer.Add(
            self.continue_button,
            pos=(6, 0),
            span=(0, 3),
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=self.border,
        )
        return grid_sizer

    def set_begin_trial_enabled(self, enabled: bool = True):
        super().set_begin_trial_enabled(enabled)
        if enabled:
            sel = self.phonemic_choice.GetSelection()
            if sel == wx.NOT_FOUND:
                self.start_video_button.Disable()
            if not self.first:
                self.set_grid_group_enable(self._main_grid, False)
        self.continue_button.Enable()

    def set_trial_running(self, running: bool) -> None:
        super().set_trial_running(running)
        if not self.first:
            self.set_grid_group_enable(self._main_grid, False)
        self.continue_button.Enable()

    def switch_panel(self) -> None:
        self.seconds = 0
        self.seconds_text.SetLabel("Time: 60 secs")
        # self._set_phonemic_task()
        logger.debug("Trial Continued; %s, %s selected", self.phonemic_list, self.semantic)
        logger.debug("value: %s", self.value)
        # self.prompt_text.Wrap(299)
        with wx.EventBlocker(self.continue_button):
            self.continue_button.SetValue(False)
        self.first = False
        self.trial_num += 1
        self.actual_list.append(self.value)
        self.start_video_button.Enable()
        self.Layout()
        self.Update()

    def update_values(self) -> None:
        logger.debug("printing update_values")
        with wx.EventBlocker(self.continue_button):
            self.continue_button.SetValue(False)
        self.start_video_button.Enable()
        self.seconds_text.SetLabel("Time: 60 secs")
        if self.trial_num < len(self.phonemic_list):
            self.value = self.phonemic_list[self.trial_num]
            self.prompt_text.SetLabel(PHONEMIC_PHRASE.replace("*", self.value))
            self.prompt_text.Wrap(299)
            logger.debug("value: %s", self.value)
        elif self.trial_num == len(self.phonemic_list):
            self.value = self.semantic
            self.prompt_text.SetLabel(SEMANTIC_PHRASE.replace("*", self.value))
            self.prompt_text.Wrap(299)
        else:
            self.prompt_text.SetLabel("Task Finished!\n Press 'End Task' button to save data.")
            self.first = True
            self.seconds_text.SetLabel(" ")
            self.continue_button.Disable()
            self.start_video_button.Disable()
            self.continue_button.Hide()
            return
        self.trial_num += 1
        self.actual_list.append(self.value)
        self.video_title.SetLabel(f"Trial: {self.value}")
        self.start_video_button.SetValue(False)
        self.start_video_button.SetLabel("Start Video")

    def get_result(self) -> str:
        return self.value

    def get_instruction(self, count: int) -> str:
        return self.value

    def add_metadata(self) -> dict[str, Any]:
        return {"phonemic_category": self.phonemic_list, "semantic_category": self.semantic}

    def on_timer(self, event: wx.Event) -> None:
        if self.trial_is_active:
            self.seconds_text.SetLabel(f"Time: {TRIAL_TIME - self.timer.value} secs")

    def get_trials(self) -> tuple[str, str, str]:
        logger.debug(
            "get_trials: %s, %s, %s", ".".join(self.phonemic_list), self.semantic, self.value
        )
        return ".".join(self.phonemic_list), self.semantic, self.value

    def run_trial(self, count: int) -> None:
        super().run_trial(count)
        self.seconds = 60

    def start_new_task(self) -> None:
        super().start_new_task()
        self.trial_num = 0
        self.seconds = 0
        self.first = True
        self.prompt_text.SetLabel("")
        self.seconds_text.SetLabel("")
        self.video_title.SetLabel("")
        self.start_video_button.SetValue(False)
        self.start_video_button.SetLabel("Start Video")
        self.start_video_button.Enable(False)
        self.Layout()
        self.Update()
