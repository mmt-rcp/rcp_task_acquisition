from typing import Any

import wx
import wx.grid

from rcp_task_acquisition.panels.TrialPanel import TrialPanel
from rcp_task_acquisition.tasks.Sara.Sara import Sara
from rcp_task_acquisition.tasks.Sara.constants import ASSESMENTS
from rcp_task_acquisition.tasks.definitions import TaskTrialClassConfig
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


class SaraPanel(TrialPanel):
    task_trial_item_config = TaskTrialClassConfig("sara", "SARA", "sara", Sara)

    def __init__(self, parent: wx.Panel) -> None:
        super().__init__(parent)
        self.current_assesment: str = ""
        self.assesment_list: list[str] = list(ASSESMENTS.keys())
        self.assesment_num = 0
        self.actual_assesments: dict[str, dict[str, Any]] = {}
        self.recent_trials: dict[str, int] = {}
        vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        vertical_sizer.Add(self._setup_panel(), 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        # vertical_sizer.Add(self.setup_instruction_playback(), 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        self.SetSizer(vertical_sizer)
        self.edit_num: str | None = None

    def populate_metadata(self, metadata: dict):
        metadata["trial_data"] = self.add_metadata()

    def _setup_panel(self):
        self.assesment_task = wx.StaticText(self, label="Choose Assesment:")
        self.assesment_choice = wx.Choice(
            self, id=wx.ID_ANY, choices=self.assesment_list, size=(310, -1)
        )

        self.continue_button = wx.ToggleButton(self, label="Begin Assesment", size=(150, -1))
        self.edit_button = wx.Button(self, label="Edit Previous Score", size=(150, -1))
        self.edit_button.Enable(False)
        self.seconds_text = wx.StaticText(self, label="Time: 0 secs", size=(300, -1))
        self.assesment_choice.SetSelection(0)
        self.assesment_choice.Bind(wx.EVT_CHOICE, lambda _: self.check_can_edit())
        grid_sizer = wx.GridBagSizer(7, 6)
        grid_sizer.Add(
            self.assesment_task,
            pos=(0, 0),
            span=(0, 2),
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.ALIGN_CENTER | wx.ALL,
            border=5,
        )
        grid_sizer.Add(
            self.assesment_choice,
            pos=(1, 0),
            span=(0, 4),
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=5,
        )
        grid_sizer.Add(
            self.seconds_text,
            pos=(2, 0),
            span=(0, 4),
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            self.continue_button,
            pos=(3, 0),
            span=(0, 3),
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            self.edit_button,
            pos=(3, 3),
            span=(0, 3),
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=self.border,
        )
        self.edit_button.Bind(wx.EVT_BUTTON, self.edit_score)
        return grid_sizer

    def show_scoring(self):
        self.scoring_panel = AssesmentPanel(self.current_assesment)
        self.scoring_panel.Bind(wx.EVT_CLOSE, self._on_reset_assessment)
        self.scoring_panel.continue_button.Bind(wx.EVT_BUTTON, self._on_reset_assessment)
        self.continue_button.Enable(False)
        self.edit_button.Enable(False)

    def add_metadata(self):
        return self.actual_assesments

    def _on_reset_assessment(self, event: wx.Event):
        self.reset_assesment()

    def reset_assesment(self) -> None:
        logger.verbose("in reset_assessment")
        button_idx, text = self.scoring_panel.get_result()
        # need to unbind to prevent infinite recursion,
        self.scoring_panel.Unbind(wx.EVT_CLOSE, handler=self._on_reset_assessment)
        # with this following Close:
        self.scoring_panel.Close()
        logger.debug(f"button: {button_idx}, text: {text}")
        assesment_dict = {
            "type": self.current_assesment,
            "score": button_idx,
            "description": ASSESMENTS[self.current_assesment][button_idx],
            "notes": text,
        }
        self.assesment_num = self.assesment_choice.GetSelection()
        if self.assesment_num < len(self.assesment_list) - 1:
            self.assesment_num += 1
        else:
            self.assesment_num = 0
        self.current_assesment = self.assesment_list[self.assesment_num]
        self.assesment_choice.SetSelection(self.assesment_num)
        logger.debug(f"edit num: {self.edit_num}")
        if self.edit_num is not None:
            self.actual_assesments[f"{self.edit_num}"] = assesment_dict
            self.edit_num = None
        else:
            self.actual_assesments[f"trial_{self.trial_number}"] = assesment_dict
        self.assesment_task.Enable(True)
        self.assesment_choice.Enable(True)
        self.continue_button.SetLabel("Begin Assesment")
        self.continue_button.Enable(True)
        self.seconds_text.SetLabel("Time: 0 secs")
        self.check_can_edit()

    def get_result(self):
        return self.current_assesment

    def run_trial(self, count: int) -> None:
        self.trial_number += 1
        logger.debug(f"trial Number: {self.trial_number}")
        self.trial_is_active = True
        self.assesment_task.Enable(False)
        self.assesment_choice.Enable(False)
        cur_asses = self.current_assesment = self.assesment_list[
            self.assesment_choice.GetSelection()
        ]
        self.continue_button.SetLabel("End Assesment")
        self.recent_trials[cur_asses] = self.trial_number

    def check_can_edit(self) -> None:
        self.assesment_num = self.assesment_choice.GetSelection()
        self.current_assesment = self.assesment_list[self.assesment_num]
        if self.assesment_list[self.assesment_num] in self.recent_trials:
            self.edit_button.Enable(True)
        else:
            self.edit_button.Enable(False)

    def reset(self, trial):
        super().reset(trial)
        self.continue_button.Enable(True)

    def on_timer(self, event):
        if self.trial_is_active:
            self.seconds += 1
            if self.seconds >= 0:
                self.seconds_text.SetLabel(f"Time: {self.timer.value} secs")

    def edit_score(self, event):
        logger.debug(f"assesment: {self.recent_trials[self.current_assesment]}")
        self.edit_num = f"trial_{self.recent_trials[self.current_assesment]}"
        args = self.actual_assesments[f"trial_{self.recent_trials[self.current_assesment]}"]
        logger.debug(f"actual a: {self.actual_assesments}")
        logger.debug(f"args: {args}")
        logger.debug(f"recent t: {self.recent_trials}")
        self.scoring_panel = AssesmentPanel(self.current_assesment, args)
        self.scoring_panel.Bind(wx.EVT_CLOSE, self._on_reset_assessment)
        self.scoring_panel.continue_button.Bind(wx.EVT_BUTTON, self._on_reset_assessment)
        self.continue_button.Enable(False)
        self.edit_button.Enable(False)


class AssesmentPanel(wx.Dialog):
    def __init__(self, current_assesment, args=None, parent=None) -> None:
        if args is None:
            args = {}
        super().__init__(parent, title="Score Assesment")
        self.vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        self.border = 7
        self.left_radio = None
        self.button_list: dict[int, wx.RadioButton] = {}
        self.vertical_sizer.Add(
            self._create_assesment_score(current_assesment, args),
            0,
            wx.ALIGN_LEFT | wx.ALL,
            self.border,
        )
        self.vertical_sizer.Add(self._add_notes(args), 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        self.vertical_sizer.Add(self._add_buttons(), 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        self.SetSizerAndFit(self.vertical_sizer)
        self.Layout()
        self.Show()

    def _create_assesment_score(self, current_assesment, args=None):
        if args is None:
            args = {}
        assesment_scores = ASSESMENTS[current_assesment]
        grid_sizer = wx.GridBagSizer(len(assesment_scores.keys()), 3)
        for score in assesment_scores:
            button = wx.RadioButton(self)
            number = wx.StaticText(self, label=str(score))
            self.button_list[score] = button
            description = wx.StaticText(self, label=assesment_scores[score])
            description.Wrap(520)
            grid_sizer.Add(
                button,
                pos=(score, 0),
                span=(0, 1),
                flag=wx.ALIGN_LEFT | wx.ALL,
                border=self.border,
            )
            grid_sizer.Add(
                number,
                pos=(score, 1),
                span=(0, 1),
                flag=wx.ALIGN_LEFT | wx.ALL,
                border=self.border,
            )
            grid_sizer.Add(
                description,
                pos=(score, 2),
                span=(0, 1),
                flag=wx.ALIGN_LEFT | wx.ALL,
                border=self.border,
            )
        if "score" in args:
            self.button_list[args["score"]].SetValue(True)
        return grid_sizer

    def _add_notes(self, args=None):
        if args is None:
            args = {}
        grid_sizer = wx.GridBagSizer(2, 4)
        notes_text = wx.StaticText(self, label="Notes:")
        self.notes = wx.TextCtrl(self, size=wx.Size(550, 100), style=wx.TE_MULTILINE | wx.TE_LEFT)
        grid_sizer.Add(
            notes_text, pos=(0, 0), span=(0, 1), flag=wx.ALIGN_LEFT | wx.ALL, border=self.border
        )
        grid_sizer.Add(
            self.notes, pos=(1, 0), span=(0, 4), flag=wx.ALIGN_LEFT | wx.ALL, border=self.border
        )
        if "notes" in args:
            self.notes.SetValue(args["notes"])
        return grid_sizer

    def _add_buttons(self):
        grid_sizer = wx.GridBagSizer(1, 4)
        self.continue_button = wx.Button(self, label="Confirm Score", size=(150, -1))

        grid_sizer.Add(
            self.continue_button,
            pos=(0, 0),
            span=(0, 2),
            flag=wx.ALIGN_CENTER | wx.ALL,
            border=self.border,
        )
        return grid_sizer

    def get_result(self) -> tuple[int, str]:
        text = self.notes.GetValue()
        button_used = -1
        for idx, button in enumerate(self.button_list):
            if self.button_list[button].GetValue():
                button_used = idx
                break
        logger.debug(f"button used: {button_used}")
        return button_used, text
