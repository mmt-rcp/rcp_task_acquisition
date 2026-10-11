from enum import Enum

import wx

from rcp_task_acquisition.models.Warnings import WarningHandler
from rcp_task_acquisition.panels.LaunchPanel import LaunchPanel
from rcp_task_acquisition.panels.MainFrame import MainFrame
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.run_context import RcpRunContext

logger = get_logger(__name__)


class ActivePanel(Enum):
    LAUNCH = True
    TASK = False


class SwitchPanel:
    """Main "switch" (control-) panel"""

    def __init__(self, *, rcp_context: RcpRunContext) -> None:
        self._rcp_context: RcpRunContext = rcp_context
        self.active_panel = True
        self.launch_panel = LaunchPanel(rcp_context=rcp_context)
        self.task_frame = MainFrame(rcp_context=rcp_context)
        self.warning = WarningHandler()

        self.disable_timer = wx.Timer(self.launch_panel.panel, wx.ID_ANY)

        self.task_frame.quit.Bind(wx.EVT_BUTTON, self.disable_panel)
        self.task_frame.Bind(wx.EVT_CLOSE, self.disable_panel)

        self.launch_panel.Show()
        self.launch_panel.protocol_button.Bind(wx.EVT_BUTTON, self.disable_panel)
        self.launch_panel.exit_button.Bind(wx.EVT_BUTTON, self.exit_event)
        self.launch_panel.dialog.Bind(wx.EVT_CLOSE, self.exit_event)
        self.launch_panel.panel.Bind(wx.EVT_TIMER, self.switch_panel, self.disable_timer)
        self.task_frame.Bind(wx.EVT_TIMER, self.switch_panel, self.disable_timer)
        self.launch_panel.panel.SetFocus()

    def switch_panel(self, event: wx.Event) -> None:
        # if launch panel showing, switching to show task panel & vice versa
        logger.verbose("switch_panel: event: %s ; from=%s", event, event.GetEventObject())
        if self.active_panel == ActivePanel.LAUNCH.value:
            self.task_frame.Enable()
            self.task_frame.quit.SetLabel("Exit to Launch Menu")
            self.launch_panel.get_metadata()
            self.task_frame.show(self.launch_panel.metadata, event)
            self.launch_panel.Hide()

        else:
            self.launch_panel.protocol_button.SetLabel("Select Protocol")
            self.launch_panel.enable_gui(True)
            self.task_frame.HideWithEvent(event)
            self.launch_panel.Show()

        self.active_panel = not self.active_panel

    def disable_panel(self, event: wx.Event) -> None:
        """
        Disable the current shown panel while enabling other panel
        """
        logger.debug("disable_panel: event=%s ; from=%s", event, event.GetEventObject())
        if self.active_panel == ActivePanel.LAUNCH.value:
            self.launch_panel.protocol_button.SetLabel("Loading...")
            self.launch_panel.enable_gui(False)
        else:
            self.task_frame.quit.SetLabel("Loading...")
            self.task_frame.Disable()
        if isinstance(event, wx.CloseEvent) and event.GetEventObject() == self.launch_panel.dialog:
            # if close of main launch panel, then don't switch panels.
            return
        if 0:
            self.switch_panel(event)  # tried this, which is indirectly called by the disable_timer,
        # but for some reason don't get the same visual result.
        self.disable_timer.StartOnce(200)

    def exit_event(self, event: wx.Event) -> None:
        self.task_frame.HideWithEvent(event)
        self.task_frame.quitButton(event)
        # prevents infinite recursion:
        self.launch_panel.dialog.Unbind(wx.EVT_CLOSE)
        # given launch_panel Close is also bound to this exit_event.
        self.launch_panel.exit_event()
        logger.verbose("about to exit")
        wx.Exit()  # really makes wx main loop to exit,
        ## required at the moment, there are still events/timers registered which can otherwise be executed
        # on already closed resources, leading to use after free exception.
        # And also: some other event handlers are making the task/protocol frame/window to be launched: fixed now.
