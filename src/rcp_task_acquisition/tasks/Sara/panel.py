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

    def __init__(self, parent: wx.Window, *args, **kwargs) -> None:
        super().__init__(parent, *args, **kwargs)
        self.current_assessment: str = ""
        self.assessment_list: list[str] = list(ASSESMENTS.keys())
        self.assessment_num = 0
        self.actual_assessments: dict[str, dict[str, Any]] = {}
        self.recent_trials: dict[str, int] = {}
        vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        vertical_sizer.Add(self._setup_panel(), 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        # vertical_sizer.Add(self.setup_instruction_playback(), 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        self.SetSizer(vertical_sizer)
        self.edit_num: str | None = None
        self.scoring_panel: AssessmentPanel | None = None

    def populate_metadata(self, metadata: dict) -> None:
        metadata["trial_data"] = self.add_metadata()

    def _setup_panel(self) -> wx.GridBagSizer:
        self.assessment_task = wx.StaticText(self, label="Choose Assessment:")
        self.assessment_choice = wx.Choice(
            self, id=wx.ID_ANY, choices=self.assessment_list, size=(310, -1)
        )

        self.continue_button = wx.ToggleButton(self, label="Begin Trial", size=(150, -1))
        self.edit_button = wx.Button(self, label="Edit Previous Score", size=(150, -1))
        self.edit_button.Enable(False)
        self.seconds_text = wx.StaticText(self, label="Time: 0 secs", size=(300, -1))
        self.assessment_choice.SetSelection(0)
        self.assessment_choice.Bind(wx.EVT_CHOICE, lambda _: self.check_can_edit())
        grid_sizer = wx.GridBagSizer(7, 6)
        grid_sizer.Add(
            self.assessment_task,
            pos=(0, 0),
            span=(0, 2),
            flag=wx.RESERVE_SPACE_EVEN_IF_HIDDEN | wx.ALIGN_CENTER | wx.ALL,
            border=5,
        )
        grid_sizer.Add(
            self.assessment_choice,
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

    def show_scoring(self) -> None:
        self.scoring_panel = AssessmentPanel(self.current_assessment)
        self.scoring_panel.Bind(wx.EVT_CLOSE, self._on_reset_assessment)
        self.scoring_panel.continue_button.Bind(wx.EVT_BUTTON, self._on_reset_assessment)
        self.continue_button.Enable(False)
        self.edit_button.Enable(False)

    def add_metadata(self) -> dict[str, dict[str, Any]]:
        return self.actual_assessments

    def _on_reset_assessment(self, event: wx.Event) -> None:
        self.reset_assessment()

    def reset_assessment(self) -> None:
        logger.verbose("in reset_assessment")
        score_panel = self.scoring_panel
        if score_panel is None:
            return
        button_idx, text = score_panel.get_result()
        # need to unbind to prevent infinite recursion,
        score_panel.Unbind(wx.EVT_CLOSE, handler=self._on_reset_assessment)
        # with this following Close:
        score_panel.Close()
        logger.debug("button: %s, text: %s", button_idx, text)
        assesment_dict = {
            "type": self.current_assessment,
            "score": button_idx,
            "description": ASSESMENTS[self.current_assessment][button_idx],
            "notes": text,
        }
        self.assessment_num = self.assessment_choice.GetSelection()
        if self.assessment_num < len(self.assessment_list) - 1:
            self.assessment_num += 1
        else:
            self.assessment_num = 0
        self.current_assessment = self.assessment_list[self.assessment_num]
        self.assessment_choice.SetSelection(self.assessment_num)
        logger.debug("edit num: %s", self.edit_num)
        if self.edit_num is not None:
            self.actual_assessments[f"{self.edit_num}"] = assesment_dict
            self.edit_num = None
        else:
            self.actual_assessments[f"trial_{self.trial_number}"] = assesment_dict
        self.assessment_task.Enable(True)
        self.assessment_choice.Enable(True)
        self.continue_button.SetLabel("Begin Trial")
        self.continue_button.Enable(True)
        self.seconds_text.SetLabel("Time: 0 secs")
        self.check_can_edit()

    def get_result(self) -> str:
        return self.current_assessment

    def run_trial(self, count: int) -> None:
        self.trial_number += 1
        logger.debug("trial Number: %s", self.trial_number)
        self.trial_is_active = True
        self.assessment_task.Enable(False)
        self.assessment_choice.Enable(False)
        cur_asses = self.current_assessment = self.assessment_list[
            self.assessment_choice.GetSelection()
        ]
        self.continue_button.SetLabel("Stop Trial")
        self.recent_trials[cur_asses] = self.trial_number

    def check_can_edit(self) -> None:
        self.assessment_num = self.assessment_choice.GetSelection()
        self.current_assessment = self.assessment_list[self.assessment_num]
        if self.assessment_list[self.assessment_num] in self.recent_trials:
            self.edit_button.Enable(True)
        else:
            self.edit_button.Enable(False)

    def reset(self, count: int) -> None:
        super().reset(count)
        self.continue_button.Enable(True)

    def on_timer(self, event: wx.Event) -> None:
        if self.trial_is_active:
            self.seconds += 1
            if self.seconds >= 0:
                self.seconds_text.SetLabel(f"Time: {self.timer.value} secs")

    def edit_score(self, event: wx.Event) -> None:
        logger.debug("assessment: %s", self.recent_trials[self.current_assessment])
        self.edit_num = f"trial_{self.recent_trials[self.current_assessment]}"
        args = self.actual_assessments[f"trial_{self.recent_trials[self.current_assessment]}"]
        logger.debug("actual a: %s", self.actual_assessments)
        logger.debug("args: %s", args)
        logger.debug("recent t: %s", self.recent_trials)
        score_panel = self.scoring_panel = AssessmentPanel(self.current_assessment, args)
        score_panel.Bind(wx.EVT_CLOSE, self._on_reset_assessment)
        score_panel.continue_button.Bind(wx.EVT_BUTTON, self._on_reset_assessment)
        self.continue_button.Enable(False)
        self.edit_button.Enable(False)


class AssessmentPanel(wx.Dialog):
    def __init__(
        self,
        current_assessment,
        args: dict[str, Any] | None = None,
        parent: wx.Window | None = None,
    ) -> None:
        if args is None:
            args = {}
        super().__init__(parent, title="Score Assessment")
        self.vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        self.border = 7
        self.left_radio = None
        self.button_list: dict[int, wx.RadioButton] = {}
        self.vertical_sizer.Add(
            self._create_assessment_score(current_assessment, args),
            0,
            wx.ALIGN_LEFT | wx.ALL,
            self.border,
        )
        self.vertical_sizer.Add(self._add_notes(args), 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        self.vertical_sizer.Add(self._add_buttons(), 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        self.SetSizerAndFit(self.vertical_sizer)
        self.Layout()
        self.Show()

    def _create_assessment_score(
        self, current_assessment: str, args: dict[str, Any]
    ) -> wx.GridBagSizer:
        logger.verbose("create assessment score: current=%s args=%s", current_assessment, args)
        if args is None:
            args = {}
        assessment_scores = ASSESMENTS[current_assessment]
        grid_sizer = wx.GridBagSizer(len(assessment_scores.keys()), 3)
        for score in assessment_scores:
            button = wx.RadioButton(self)
            number = wx.StaticText(self, label=str(score))
            self.button_list[score] = button
            description = wx.StaticText(self, label=assessment_scores[score])
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

    def _add_notes(self, args=None) -> wx.GridBagSizer:
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

    def _add_buttons(self) -> wx.GridBagSizer:
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
        logger.debug("button used: %s", button_used)
        return button_used, text
