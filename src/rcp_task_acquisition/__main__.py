import sys
import threading
from pathlib import Path

# import matplotlib
import wx.adv

import wx

# set up matplotlib to be compatible on commandline/spyder
# matplotlib.use("qtagg")


class App(wx.App):
    """RCP Task Acquisition"""

    def __init__(self):
        self._action_thread: None | threading.Thread = None
        self._load_app_dialog: wx.Dialog
        super().__init__()

    def _show_start_dialog(self):
        diag = self._load_app_dialog = wx.Dialog(
            parent=None,
            title="Loading application",
        )
        diag.SetSize(wx.GetDisplaySize())
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
            1,
            wx.ALIGN_CENTER_HORIZONTAL | wx.ALL,
            0,
        )
        sizer.AddStretchSpacer(2)
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

    def _check_repo_status(self):
        from rcp_task_acquisition.utils.repo import check_repo_up_to_date

        rcp_package_dir = Path(__file__).parent
        if rcp_package_dir.parent.name == "src":
            warn_msg = (
                "Warning: Your program is a different version than the latest available version. "
                "Please make sure to update as soon as possible"
            )
            repo_dir = rcp_package_dir.parent.parent
            up2date_status = check_repo_up_to_date(
                repo_dir,
                m_ahead=warn_msg,
                m_behind=warn_msg,
                m_diverged=warn_msg,
                m_diff_branch=warn_msg,
                m_detached=warn_msg,
                m_up2date_but_dirty=None,
            )
        else:
            # could be a wheel install.. todo
            up2date_status = None
        if up2date_status is not None:
            wx.CallAfter(lambda: wx.MessageBox(up2date_status, style=wx.STAY_ON_TOP))

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
        self._check_repo_status()

        from rcp_task_acquisition.panels.SwitchPanel import SwitchPanel  # delayed import on purpose

        self.SwitchPanel = SwitchPanel
        wx.CallAfter(self.OnLoadDone)  # must be executed in main UI thread

    def OnLoadDone(self):
        panel = self.SwitchPanel()
        self._load_app_dialog.Hide()
        self._load_app_dialog.Close()


def run_app():
    app = App()
    return app.MainLoop()


if __name__ == "__main__":
    sys.exit(run_app())
