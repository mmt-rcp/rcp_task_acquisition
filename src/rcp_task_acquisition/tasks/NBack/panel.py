from datetime import datetime

import wx

from rcp_task_acquisition.panels.TrialPanel import TrialPanel
from rcp_task_acquisition.tasks.NBack.NBack import N_back
from rcp_task_acquisition.tasks.NBack.configs import NBACK_TYPES
from rcp_task_acquisition.tasks.definitions import TaskTrialClassConfig
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


class NbackPanel(TrialPanel):
    task_trial_item_config = TaskTrialClassConfig("n_back", "Nback", "nback", N_back)

    def __init__(self, parent=None, *args, **kwargs):
        super().__init__(parent, *args, **kwargs)
        self.trial_type = "real"
        vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        vertical_sizer.Add(self._setup_nback(), 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        self.SetSizer(vertical_sizer)

    def _setup_nback(self):
        self.choice_list = ["1-back", "2-back"]

        self.practice = wx.RadioButton(self, label="Practice Trial", style=wx.RB_GROUP)
        self.real = wx.RadioButton(self, label="Real Trial")

        trial = wx.StaticText(self, label="Select N-back")
        self.nback_choice = wx.Choice(self, id=wx.ID_ANY, choices=NBACK_TYPES, size=(200, -1))
        self.nback_choice.SetSelection(0)

        text = wx.StaticText(self, label="Select trial type")
        self.continue_button = wx.ToggleButton(self, label="Start Trial")

        grid_sizer = wx.GridBagSizer(5, 4)

        grid_sizer.Add(trial, pos=(0, 0), span=(0, 2), flag=wx.ALIGN_LEFT | wx.ALL, border=10)
        grid_sizer.Add(
            self.nback_choice,
            pos=(0, 2),
            span=(0, 2),
            flag=wx.ALIGN_LEFT | wx.TOP | wx.BOTTOM,
            border=10,
        )

        grid_sizer.Add(text, pos=(1, 0), span=(0, 4), flag=wx.ALIGN_LEFT | wx.ALL, border=10)
        grid_sizer.Add(
            self.practice,
            pos=(2, 0),
            span=(0, 2),
            flag=wx.ALIGN_LEFT | wx.TOP | wx.BOTTOM,
            border=10,
        )
        grid_sizer.Add(
            self.real, pos=(2, 2), span=(0, 2), flag=wx.ALIGN_LEFT | wx.TOP | wx.BOTTOM, border=10
        )
        grid_sizer.Add(
            self.continue_button, pos=(4, 0), span=(0, 2), flag=wx.ALIGN_LEFT | wx.TOP, border=10
        )
        return grid_sizer

    def get_result(self) -> tuple[str, str]:
        self.trial_type = "practice" if self.practice.GetValue() else "real"
        return self.trial_type, NBACK_TYPES[self.nback_choice.GetSelection()]

    def run_trial(self, count: int) -> None:
        self.nback_choice.Enable(False)
        self.practice.Enable(False)

    def reset(self, count: int) -> None:
        self.nback_choice.Enable(True)
        self.practice.Enable(True)
        self.continue_button.Enable(True)
        self.continue_button.Enable(True)
        self.continue_button.SetValue(False)
        self.continue_button.SetLabel("Start Trial")
