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

        self.task_frame.quit.Bind(wx.EVT_BUTTON, self._on_disable_panel)
        self.task_frame.Bind(wx.EVT_CLOSE, self._on_disable_panel)

        self.launch_panel.Show()
        self.launch_panel.protocol_button.Bind(wx.EVT_BUTTON, self._on_disable_panel)
        self.launch_panel.exit_button.Bind(wx.EVT_BUTTON, self._on_exit)
        self.launch_panel.dialog.Bind(wx.EVT_CLOSE, self._on_exit)
        self.launch_panel.panel.Bind(wx.EVT_TIMER, self._on_switch_panel, self.disable_timer)
        self.task_frame.Bind(wx.EVT_TIMER, self._on_switch_panel, self.disable_timer)
        self.launch_panel.panel.SetFocus()

    def _on_exit(self, _: wx.Event) -> None:
        self.exit_event()

    def _on_switch_panel(self, event: wx.Event) -> None:
        logger.verbose("switch_panel: event: %s ; from=%s", event, event.GetEventObject())
        self.switch_panel()

    def switch_panel(self) -> None:
        # if launch panel showing, switching to show task panel & vice versa
        if self.active_panel == ActivePanel.LAUNCH.value:
            self.task_frame.Enable()
            self.task_frame.quit.SetLabel("Exit to Launch Menu")
            self.launch_panel.get_metadata()
            self.task_frame.show(self.launch_panel.metadata)
            self.launch_panel.Hide()
        else:
            self.launch_panel.protocol_button.SetLabel("Select Protocol")
            self.launch_panel.enable_gui(True)
            self.task_frame.Hide()
            self.launch_panel.Show()

        self.active_panel = not self.active_panel

    def _on_disable_panel(self, event: wx.Event):
        logger.verbose("on_disable_panel: event=%s ; from=%s", event, event.GetEventObject())
        self.disable_panel()
        if isinstance(event, wx.CloseEvent) and event.GetEventObject() == self.launch_panel.dialog:
            logger.debug("close from launch panel, preventing timer start")
            # if close of main launch panel, then don't switch panels.
            return
        if 0:
            self.switch_panel()  # tried this, which is indirectly called by the disable_timer,
        # but for some reason don't get the same visual result.
        self.disable_timer.StartOnce(200)

    def disable_panel(self) -> None:
        """
        Disable the current shown panel while enabling other panel
        """
        if self.active_panel == ActivePanel.LAUNCH.value:
            self.launch_panel.protocol_button.SetLabel("Loading...")
            self.launch_panel.enable_gui(False)
        else:
            self.task_frame.quit.SetLabel("Loading...")
            self.task_frame.Disable()

    def exit_event(self) -> None:
        self.task_frame.Hide()
        self.task_frame.quitButton()
        # prevents infinite recursion:
        self.launch_panel.dialog.Unbind(wx.EVT_CLOSE)
        # given launch_panel Close is also bound to this exit_event.
        self.launch_panel.exit_event()
        logger.verbose("about to exit")
        wx.Exit()  # really makes wx main loop to exit,
        ## required at the moment, there are still events/timers registered which can otherwise be executed
        # on already closed resources, leading to use after free exception.
        # And also: some other event handlers are making the task/protocol frame/window to be launched: fixed now.
