import os
from pathlib import Path

import wx

from rcp_task_acquisition.tasks.NaturalisticSpeech import constants
from rcp_task_acquisition.panels.TrialPanel import TrialPanel
from rcp_task_acquisition.tasks.NaturalisticSpeech.NaturalisticSpeech import NaturalisticSpeech
from rcp_task_acquisition.tasks.definitions import TaskTrialClassConfig
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


_accepted_images_ext = (
    ".jpg",
    ".jpeg",
    ".png",
)


class NaturalisticSpeechPanel(TrialPanel):
    task_trial_item_config = TaskTrialClassConfig(
        "naturalistic_speech", "Naturalistic Speech", "naturalisticspeech", NaturalisticSpeech
    )

    def __init__(self, parent: wx.Window, *args, **kwargs) -> None:
        super().__init__(parent, *args, **kwargs)
        self.seconds = 0
        self.display_secs = 0
        self.display_mins = 0
        self.trial_number = 1
        self.countdown_start = 0
        self._image_paths: list[str] = []
        self._image_names: list[str] = []
        self.border = 5
        self.photo = None
        self.selection = 0
        vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        main_grid = self._main_grid = self._set_up_photo()
        vertical_sizer.Add(main_grid, 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        self.SetSizer(vertical_sizer)

    def _set_up_photo(self) -> wx.GridBagSizer:
        """
        Set up the naturalistic speech panel
        Returns:
            message (wx dialog panel)
        """
        images = list(
            imp for imp in constants.IMG_DIR.glob("*") if imp.name.endswith(_accepted_images_ext)
        )
        image_paths = self._image_paths = []
        image_names = self._image_names = []
        for imp in images:
            image_paths.append(imp.as_posix())
            image_names.append(imp.name)
        image_names.extend(constants.NON_IMAGE_TASKS)
        self.image_choice = wx.Choice(self, id=wx.ID_ANY, choices=image_names, size=(310, -1))
        self.image_choice.SetSelection(self.selection)

        wx_image = wx.Image(self._image_paths[self.selection], wx.BITMAP_TYPE_ANY)
        wx_image = wx_image.Scale(250, 150)
        self.shown_image = wx.StaticBitmap(self, wx.ID_ANY, wx_image)

        self.image_choice.Bind(wx.EVT_CHOICE, self.update_image)
        self.trial_text = wx.StaticText(self, label="Trial # 1")

        photo_text = wx.StaticText(self, label="Choose which photo to show:")
        self.seconds_text = wx.StaticText(self, label="Time: 0 mins, 0 secs")

        grid_sizer = wx.GridBagSizer(5, 4)

        grid_sizer.Add(
            photo_text, pos=(0, 0), span=(0, 4), flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border=10
        )

        grid_sizer.Add(
            self.trial_text,
            pos=(1, 0),
            span=(0, 4),
            flag=wx.ALIGN_LEFT | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            self.shown_image,
            pos=(2, 0),
            span=(0, 4),
            flag=wx.ALIGN_CENTER | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            self.image_choice,
            pos=(3, 0),
            span=(0, 4),
            flag=wx.ALIGN_LEFT | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            self.seconds_text, pos=(4, 0), span=(0, 4), flag=wx.ALIGN_LEFT | wx.ALL, border=10
        )
        self._buttons_grid.Detach(self.continue_button)
        grid_sizer.Add(
            self.continue_button, pos=(5, 0), span=(0, 4), flag=wx.ALIGN_LEFT | wx.ALL, border=10
        )

        return grid_sizer

    def run_trial(self, count: int) -> None:
        super().run_trial(count)
        self.seconds = 0
        self.trial_number = count
        self.trial_is_active = True
        self.image_choice.Enable(False)
        self.shown_image.Enable(False)
        self.trial_text.SetLabel(f"Trial # {self.trial_number}")

    def get_result(self) -> tuple[str, int]:
        image_path = self._image_names[self.selection]
        return image_path, self.trial_number

    def reset(self, count: int) -> None:
        super().reset(count)
        self.trial_number = count
        self.trial_is_active = False
        self.seconds_text.SetLabel("Time: 0 mins, 0 secs")
        self.image_choice.Enable(True)
        self.shown_image.Enable(True)
        self.trial_text.SetLabel(f"Trial # {self.trial_number}")

    def on_timer(self, event: wx.Event) -> None:
        # self.seconds+=1
        self.display_mins = int(self.timer.value / 60)
        self.display_secs = self.timer.value % 60
        if self.trial_is_active:
            self.seconds_text.SetLabel(f"Time: {self.display_mins} mins, {self.display_secs} secs")

    def update_image(self, event: wx.Event) -> None:
        self.selection = self.image_choice.GetSelection()
        if self.selection >= len(self._image_paths):
            wx_image = wx.Image(250, 250, clear=True)
        else:
            wx_image = wx.Image(self._image_paths[self.selection], wx.BITMAP_TYPE_ANY)
        wx_image = wx_image.Scale(250, 150)
        wx_image.ConvertToBitmap()

        self.shown_image.SetBitmap(wx_image)
        self.Layout()
