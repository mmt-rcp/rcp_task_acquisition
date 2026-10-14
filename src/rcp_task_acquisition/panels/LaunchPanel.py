from typing import Any

import wx
import wx.lib.scrolledpanel as scrolled

from rcp_task_acquisition.models.participant import Participant
from rcp_task_acquisition.panels.HardwarePanel import HardwarePanel
from rcp_task_acquisition.panels.ParticipantPanel import ParticipantPanel
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.run_context import RcpRunContext

logger = get_logger(__name__)


class LaunchPanel:
    """
    The initial launch panel where the user sets up the basic metadata and selects
    the protocol to run.

    Attributes:
        task (str):
            Current task name (based on taskconfig names)
        task_list (list[int]):
            list of tasks from the taskconfig.yaml
        protocol_choice (wx.Choice):
            dropdown for the possible task selections
        administrator_id (wx.TextCtrl):
            text box for the administrator id. final string will be added to the metadata
        participant_id (wx.ComboBox):
            Drop down to select the participants. the participant Id will be added to the metadata, the rest of the info is stored in a db
        participant_detail (wx.TextCtrl):
            text box for any overarching participant notes. final string will be added to the metadata
    """

    def __init__(self, parent=None, *, rcp_context: RcpRunContext):
        self._rcp_context = rcp_context
        self.args = None
        self.task: str = ""
        self.is_hidden = False
        tasks_config = rcp_context.tasks_config
        self.task_list = list(tasks_config.keys())
        self.task_list.append("all_hardware")
        self.protocol_choice: wx.Choice
        self.metadata: dict[str, Any] = {
            "task": "",
            "administrator_id": None,
            "participant_id": None,
            "participant_detail": None,
        }
        # Basic panel set up. 3 different steps (Protocol, metadata and buttons) to help with
        # organization and padding between sections
        self.participant_panel = ParticipantPanel(None, rcp_context=self._rcp_context)
        self.participant_id_show_list: list[str] = []
        self.participants_list: list[Participant] = []
        self.current_list: list[Participant] = []
        button_width = wx.Size(220, -1)
        self.update_list_bool = True
        self.ignore_pop_up = False
        self.dialog = wx.Dialog(parent, id=wx.ID_ANY, title="Select Protocol", pos=(660, 275))
        self.dialog.SetMaxSize(wx.Size(*wx.DisplaySize()))

        self.panel = scrolled.ScrolledPanel(self.dialog, -1, style=wx.SUNKEN_BORDER)
        self.panel.SetupScrolling(
            scroll_x=True, scroll_y=True, scrollToTop=True, scrollIntoView=False
        )
        self.hardware_panel = HardwarePanel(tasks_config, self.panel, rcp_context=self._rcp_context)
        self.hardware_panel.Hide()
        vertical_sizer = self._vert_sizer = wx.BoxSizer(wx.VERTICAL)
        vertical_sizer.Add(self._setup_metadata(button_width), 0, wx.EXPAND | wx.ALL, 10)
        vertical_sizer.Add(self._setup_buttons(), 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 30)
        vertical_sizer.Add(self.hardware_panel, 0, wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, 30)
        self._resize_dialog()

    def get_participants(self) -> None:
        self.participant_id_show_list, self.participants_list = (
            self.participant_panel.get_all_participants()
        )
        logger.info(f"show_id: {self.participant_id_show_list}, list: {self.participants_list}")
        self._set_participants_in_combo(self.participants_list)

    def _setup_metadata(self, button_width: wx.Size) -> wx.GridBagSizer:
        box = self.panel  # wx.StaticBox(self.panel)
        self.protocol_text = wx.StaticText(box, label="Protocol:")
        self.protocol_choice = wx.Choice(box, id=wx.ID_ANY, choices=self.task_list, size=(220, -1))
        self.protocol_choice.Bind(wx.EVT_CHOICE, self.task_event)
        self.protocol_choice.SetSelection(0)
        self.protocol_button = wx.Button(box, size=button_width, label="Select Protocol")
        self.task_event("")

        self.administrator_text = wx.StaticText(box, label="Administrator Id:")
        self.administrator_id = wx.TextCtrl(box, size=wx.Size(450, -1), style=wx.TE_LEFT, value="")

        self.participant_id_text = wx.StaticText(box, label="Participant:")
        combo = self.participant_id = wx.ComboBox(
            box, size=wx.Size(450, -1), style=wx.CB_DROPDOWN, choices=[]
        )
        self.get_participants()

        # combo.Bind(wx.EVT_TEXT, self.update_list)
        # combo.Bind(wx.EVT_TEXT_ENTER, self.on_enter)
        # combo.Bind(wx.EVT_COMBOBOX, )
        combo.Bind(wx.EVT_COMBOBOX, self._participant_id_combo_event)
        # # combo.Bind(wx.EVT_CHAR, combo_char)
        # def combo_change(v, orig=combo.ChangeValue):
        #     logger.debug("in combo change")
        #     orig(v)
        #     combo.SetInsertionPointEnd()
        #     combo.GetParent().SetCursor(wx.Cursor(wx.CURSOR_ARROW))
        #     combo.SetFocus()
        #
        # combo.ChangeValue = combo_change

        # self.participant_id.Bind(wx.EVT_COMBOBOX_DROPDOWN, self.on_dropdown)
        self.participant_remove = wx.Button(box, size=button_width, label="Remove Participant")
        self.participant_add = wx.Button(box, size=button_width, label="Add New Participant")
        self.participant_add.Bind(wx.EVT_BUTTON, self.add_participant)
        self.participant_remove.Bind(wx.EVT_BUTTON, self.remove_participant)
        self.participant_detail_text = wx.StaticText(box, label="Participant Details:")
        self.participant_detail = wx.TextCtrl(
            box, size=wx.Size(450, 70), style=wx.TE_MULTILINE | wx.TE_LEFT, value=""
        )

        grid_sizer = wx.GridBagSizer(4, 3)
        grid_sizer.Add(
            self.protocol_text,
            pos=(0, 0),
            span=(0, 1),
            flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=5,
        )
        grid_sizer.Add(
            self.protocol_choice,
            pos=(0, 1),
            span=(0, 1),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=5,
        )
        grid_sizer.Add(
            self.protocol_button,
            pos=(0, 2),
            span=(0, 1),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=5,
        )
        grid_sizer.Add(
            self.administrator_text,
            pos=(1, 0),
            span=(0, 1),
            flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=5,
        )
        grid_sizer.Add(
            self.administrator_id,
            pos=(1, 1),
            span=(0, 3),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=5,
        )
        grid_sizer.Add(
            self.participant_id_text,
            pos=(2, 0),
            span=(0, 1),
            flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=5,
        )
        grid_sizer.Add(
            self.participant_id,
            pos=(2, 1),
            span=(0, 3),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=5,
        )
        grid_sizer.Add(
            self.participant_remove,
            pos=(3, 1),
            span=(0, 1),
            flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=5,
        )
        grid_sizer.Add(
            self.participant_add,
            pos=(3, 2),
            span=(0, 1),
            flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=5,
        )

        grid_sizer.Add(
            self.participant_detail_text,
            pos=(4, 0),
            span=(0, 1),
            flag=wx.ALIGN_RIGHT | wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=5,
        )
        grid_sizer.Add(
            self.participant_detail,
            pos=(4, 1),
            span=(0, 3),
            flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL,
            border=5,
        )
        return grid_sizer

    def _participant_id_combo_event(self, event):
        return
        # TODO
        # combo = self.participant_id
        # idx = combo.GetSelection()
        # if idx < 0:
        #     part = None
        # else:
        #     part: Participant = combo.GetClientData(idx)
        # with wx.EventBlocker(combo):
        #     combo.SetLabelText("" if part is None else f"ParticipantId: {part.id}")
        #     # NB: this also reset the current Selection..
        # self._selected_participant = part

    def _setup_buttons(self) -> wx.BoxSizer:
        button_width = wx.Size(200, -1)
        box = self.panel  # wx.StaticBox(self.panel)
        self.hardware_button = wx.ToggleButton(box, size=button_width, label="Update Hardware")
        self.hardware_button.Bind(wx.EVT_TOGGLEBUTTON, self.hardware_event)

        self.compress_button = wx.Button(box, size=button_width, label="Compress Videos")
        self.compress_button.Enable(False)

        self.exit_button = wx.Button(box, size=button_width, label="Exit")

        row_sizer = wx.BoxSizer(wx.HORIZONTAL)
        row_sizer.Add(self.hardware_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        row_sizer.Add(self.compress_button, 0, wx.ALIGN_CENTER_VERTICAL | wx.RIGHT, 10)
        row_sizer.Add(self.exit_button, 0, wx.ALIGN_CENTER_VERTICAL)
        return row_sizer

    def _resize_dialog(self) -> None:
        self.panel.SetSizerAndFit(self._vert_sizer)
        self.hardware_panel.Fit()
        self.panel.Fit()
        self.dialog.Fit()

    def _set_participants_in_combo(
        self, participants: list[Participant], participants_display: list[str] | None = None
    ) -> None:
        if participants_display is None:
            participants_display = [
                f"Id: {part.id}, Name: Last: {part.last_name}, First: {part.first_name}"
                for part in participants
            ]
        combo = self.participant_id
        with wx.EventBlocker(combo):
            combo.Clear()
            for part_disp, part in zip(participants_display, participants):
                combo.Append(part_disp, clientData=part)

    def update_list(self, event: wx.Event) -> None:
        combo = self.participant_id
        current_text = combo.GetValue()
        insertion_point = combo.GetInsertionPoint()
        logger.info("current_text: %s - %s", current_text, combo.GetSelection())
        self.current_list = [
            part
            for part_display, part in zip(self.participant_id_show_list, self.participants_list)
            if current_text in part_display.lower()
        ]
        combo.Freeze()
        try:
            self._set_participants_in_combo(self.current_list)
            with wx.EventBlocker(combo):
                if len(self.current_list) == 1:
                    combo.SetSelection(0)
                else:
                    combo.Popup()
                    combo.SetValue(current_text)
        finally:
            combo.Thaw()

        def after():
            logger.debug("after: %s %s", combo.GetValue(), combo.GetSelection())
            combo.SetFocus()
            # combo.GetParent().SetCursor(wx.Cursor(wx.CURSOR_ARROW))
            # combo.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
            # # combo.SetInsertionPoint(insertion_point)
            # # combo.SetFocus()
            # # combo.GetParent().SetCursor(wx.Cursor(wx.CURSOR_ARROW))
            # # combo.SetCursor(wx.Cursor(wx.CURSOR_ARROW))
            # act = wx.UIActionSimulator()
            # # with wx.EventBlocker(combo):
            # act.MouseClick()
            # act.KeyDown(wx.WXK_END)
            # act.KeyUp(wx.WXK_END)
            # key_e = wx.KeyEvent(wx.wxEVT_KEY_DOWN)
            # key_e.SetKeyCode(wx.WXK_END)
            # combo.ProcessEvent(key_e)
            # key_e = wx.KeyEvent(wx.wxEVT_KEY_UP)
            # key_e.SetKeyCode(wx.WXK_END)
            # combo.ProcessEvent(key_e)
            # combo.Refresh()

        wx.CallAfter(after)

    def on_enter(self, event: wx.Event) -> None:
        logger.verbose("on_enter: %s", event.GetEventObject())

    def remove_participant(self, event: wx.Event) -> None:
        combo = self.participant_id
        idx = combo.GetSelection()
        if idx < 0:
            return
        part = combo.GetClientData(idx)
        dlg = wx.MessageDialog(
            None,
            f"Are you sure you want to delete {part.id}?",
            "Warning",
            wx.YES_NO | wx.ICON_QUESTION,
        )
        if dlg.ShowModal() == wx.ID_NO:
            return
        self.participant_panel.remove_participant(part.id)
        with wx.EventBlocker(combo):
            combo.SetSelection(-1)
            self.get_participants()

    def enable_gui(self, is_enabled) -> None:
        self.hardware_button.Enable(is_enabled)
        # self.compress_button.Enable(is_enabled)
        self.exit_button.Enable(is_enabled)
        self.administrator_text.Enable(is_enabled)
        self.administrator_id.Enable(is_enabled)
        self.participant_id_text.Enable(is_enabled)
        self.participant_id.Enable(is_enabled)
        self.participant_detail_text.Enable(is_enabled)
        self.participant_detail.Enable(is_enabled)
        self.protocol_button.Enable(is_enabled)
        self.protocol_choice.Enable(is_enabled)
        self.protocol_text.Enable(is_enabled)
        self.participant_add.Enable(is_enabled)
        self.participant_remove.Enable(is_enabled)
        self.hardware_button.SetValue(False)
        self.hardware_button.SetLabel("Update Hardware")
        self.panel.Update()

    def exit_event(self) -> None:
        logger.debug("LaunchPanel exit")
        self.panel.Close(True)
        self.participant_panel.dialog.Close(True)
        self.hardware_panel.Close(True)
        self.dialog.Close(True)

    def add_participant(self, event: wx.Event) -> None:
        self.participant_panel.show()
        participant_id = self.participant_panel.participant_id
        new_index = -1
        self.get_participants()
        for index, participant in enumerate(self.participants_list):
            if participant_id == participant.id:
                new_index = index
                break
        with wx.EventBlocker(self.participant_id):
            self.participant_id.SetSelection(new_index)

    def hardware_event(self, event):
        """
        triggers showing the hardware panel

        """
        is_pressed = self.hardware_button.GetValue()
        if is_pressed:
            self.hardware_button.SetLabel("Close Hardware Panel")
            self.hardware_panel.Show()
            self.hardware_panel.reset_hardware()

        else:
            self.hardware_button.SetLabel("Update Hardware")
            self.hardware_panel.Hide()
        self._resize_dialog()

    def task_event(self, event):
        self.task = self.task_list[self.protocol_choice.GetCurrentSelection()]
        self.hardware_panel.set_task(self.task)

    def Show(self):
        self.is_hidden = False
        return self.dialog.Show()

    def get_metadata(self) -> None:
        combo = self.participant_id
        participant_id = None
        participant = None
        idx = combo.GetSelection()
        if idx >= 0:
            part = combo.GetClientData(idx)
            for participant in self.participants_list:
                if participant.id == part.id:
                    participant_id = part.id
                    break
        self.protocol_button.Enable(False)
        self.hardware_panel.Hide()
        logger.info(f"participant panel: {self.participants_list}")
        self.hardware_button.Enable(False)
        self.panel.Refresh()
        self.metadata["task"] = self.task
        self.metadata["administrator_id"] = self.administrator_id.GetValue()
        self.metadata["participant_id"] = participant_id
        self.metadata["participant"] = participant
        self.metadata["participant_detail"] = self.participant_detail.GetValue()
        self._resize_dialog()

    def Hide(self):
        self.dialog.Hide()
