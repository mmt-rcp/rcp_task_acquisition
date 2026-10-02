import os
import multiprocessing
import shlex
import sys
import threading
from pathlib import Path

import wx
import wx.adv

from rcp_task_acquisition.utils import config
from rcp_task_acquisition.utils.run_context import RcpRunContext

from rcp_task_acquisition.utils.constants import get_rcp_config

# set up matplotlib to be compatible on commandline/spyder
# import matplotlib
# matplotlib.use("qtagg")


class App(wx.App):
    """RCP Task Acquisition"""

    def __init__(self, rcp_context: RcpRunContext):
        self._action_thread: None | threading.Thread = None
        self._load_app_dialog: wx.Dialog
        self._rcp_context = rcp_context
        super().__init__()

    def _show_start_dialog(self):
        diag = self._load_app_dialog = wx.Dialog(
            parent=None,
            title="Loading application",
        )
        # diag.SetSize(wx.GetDisplaySize())
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
            wx.MessageBox(up2date_status, style=wx.STAY_ON_TOP)

    def OnInit(self):
        self._check_repo_status()

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
        panel = self.SwitchPanel(rcp_context=self._rcp_context)
        self._load_app_dialog.Hide()
        self._load_app_dialog.Close()


def run_app():
    from rcp_task_acquisition.utils.constants import get_rcp_config
    from rcp_task_acquisition.utils import logging, trial

    console_start_log_level = os.getenv("RCP_CONSOLE_LOG_LEVEL", "INFO")
    logging.setup_logging(
        multiprocess_enabled=True,
        date_format=logging.DateTimeFormats.hour_time_precise,
        time_precision=3,
        console_handler_level=console_start_log_level,
    )

    user_cfg_path, user_cfg, task_cfg_path, tasks_cfg = config.load_rcp_config()
    rcp_context = RcpRunContext(
        config_file_path=user_cfg_path,
        user_config=user_cfg,
        tasks_config=tasks_cfg,
    )

    log_file_path = trial.get_new_log_file(unit_serial=user_cfg.unitRef)
    log_q_listener = logging.get_log_queue_listener()
    if log_q_listener is not None:
        log_q_listener.add_file_handler(
            log_file_path,
            formatter=logging.PreciseTimeFormatter(
                logging.MULTIPROC_LOG_FORMAT,
                datefmt=logging.DateTimeFormats.hour_time_precise,
                time_precision=3,
            ),
        )

    logger = logging.get_verbose_logger("rcp")
    logger.notice("Starting application..")

    # todo
    # logger.notice("Activated app_model with version %s", app_version)
    logger.debug("start cmdline=%s", shlex.join(sys.argv))
    logger.debug("start env:\n%s", "\n".join(f"{k}={v!r}" for k, v in os.environ.items()))

    rc = -1

    try:
        app = App(rcp_context=rcp_context)
        logger.info("Running main loop..")
        rc = app.MainLoop()
        logger.verbose("app main loop returned %s", rc)
        return rc
    except KeyboardInterrupt:
        logger.notice("interrupted by user / keyboard interrupt from:", exc_info=True)
    except SystemExit:
        logger.notice("interrupted by system exit from:", exc_info=True)
    except BaseException as err:
        logger.exception("Fatal error: %s", err)
        rc = 1
    finally:
        (logger.success if rc == 0 else logger.error)("exiting application with exitcode=%s", rc)
        logger.debug("closing log manager..")
        try:
            logging.stop_multiproc_logging()
        finally:
            # logging.setup_logging()
            try:
                ctx = multiprocessing.get_context()
                mgr = ctx.Manager()
                # logger.info("ctx=%s mgr=%s", ctx, mgr)
                # logger.info("%s - %s", vars(ctx), vars(mgr))
                mgr.shutdown()
            except BaseException as err:  # noqa
                # logger.exception("while shutting down multiproc manager: %s", err)
                pass
    return rc


if __name__ == "__main__":
    sys.exit(run_app())
