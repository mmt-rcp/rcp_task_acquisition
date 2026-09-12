import threading
from typing import Optional

import matplotlib
import wx.adv

# set up matplotlib to be compatible on commandline/spyder
matplotlib.use("qtagg")


class App(wx.App):
    """RCP Task Acquisition"""

    def __init__(self):
        self._action_thread: Optional[threading.Thread] = None
        self._load_app_dialog: wx.Dialog
        super().__init__()

    def _show_start_dialog(self):
        diag = self._load_app_dialog = wx.Dialog(parent=None, title="Loading application")
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.AddStretchSpacer()
        txt = wx.StaticText(
            diag,
            label="Please wait while loading in progress ...",
            style=wx.ALIGN_CENTER | wx.FONTFLAG_BOLD,
        )
        txt.SetFont(wx.Font(14, wx.FONTFAMILY_DEFAULT, wx.FONTSTYLE_NORMAL, wx.FONTWEIGHT_NORMAL))
        sizer.Add(
            txt,
            0,
            wx.ALIGN_CENTER_HORIZONTAL | wx.ALL,
            0,
        )
        sizer.AddStretchSpacer()
        diag.SetSizer(sizer)
        diag.Show()
        diag.EnableCloseButton(False)
        diag.EnableMinimizeButton(False)
        diag.EnableMaximizeButton(False)
        diag.EnableFullScreenView(False)
        diag.EnableVisibleFocus(False)

    def _show_splash_screen(self):
        img = wx.Image("loading.png", wx.BITMAP_TYPE_ANY)
        bitmap = wx.Bitmap(img)

        # Use wx.adv for both the class and the styling flags
        splash = wx.adv.SplashScreen(
            bitmap,
            wx.adv.SPLASH_CENTRE_ON_SCREEN | wx.adv.SPLASH_TIMEOUT,
            3000,  # Duration in milliseconds (3 seconds)
            None,
            -1,
        )
        splash.Show()

    def OnInit(self):
        if False:
            # eventually use image from file:
            self._show_splash_screen()
        else:
            self._show_start_dialog()
        # # The event loop needs to yield control briefly to let the splash screen paint itself
        # wx.Yield()  # not necessary, given doing import(s) in sub-thread:
        # start sub-thread for import(s):
        th = threading.Thread(target=self._load_imports, daemon=True)
        self._action_thread = th
        th.start()
        return True

    def _load_imports(self):
        from rcp_task_acquisition.panels.SwitchPanel import SwitchPanel  # delayed import on purpose

        self.SwitchPanel = SwitchPanel
        wx.CallAfter(self.OnLoadDone)  # must be executed in main UI thread

    def OnLoadDone(self):
        panel = self.SwitchPanel()
        self._load_app_dialog.Hide()
        self._load_app_dialog.Close()


def run_app():
    app = App()
    app.MainLoop()


if __name__ == "__main__":
    run_app()
