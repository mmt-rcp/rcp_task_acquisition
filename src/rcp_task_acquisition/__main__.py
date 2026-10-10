import multiprocessing
import os
import shlex
import sys
import threading
import time
from pathlib import Path

import wx
import wx.adv

from rcp_task_acquisition.utils import config, logging, trial, constants
from rcp_task_acquisition.utils.run_context import RcpRunContext
from rcp_task_acquisition.utils.task_acquisistion_version import __version__ as app_version

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
    from rcp_task_acquisition import cmdline

    args = cmdline.parse_args()

    cfg_dir = args.config_dir
    if cfg_dir is None:
        cfg_dir = Path(constants.CODE_CONFIG_DIR_PATH)

    console_start_log_level = (
        os.getenv("RCP_CONSOLE_LOG_LEVEL", "INFO") if args.log_level is None else args.log_level
    )
    logging.setup_logging(
        multiprocess_enabled=True,
        date_format=logging.DateTimeFormats.hour_time_precise,
        time_precision=3,
        console_handler_level=console_start_log_level,
    )

    logger = logging.get_verbose_logger("rcp")
    logger.notice("Starting application.. version=%s", app_version)
    logger.debug("start cmdline=%s", shlex.join(sys.argv))
    logger.debug("start env:\n%s", "\n".join(f"{k}={v!r}" for k, v in os.environ.items()))

    logger.info("Loading config from %s", cfg_dir)
    try:
        user_cfg_data, tasks_cfg_data = config.load_rcp_config(cfg_dir)
        user_cfg = user_cfg_data[0]
    except BaseException as err:
        # save_err = err
        user_cfg_data = tasks_cfg_data = None
        logger.error("Could not load config from %s: %s", cfg_dir, err)
        user_cfg = config.RcpUserConfig(unitRef="unitME", RawDataDir=constants.DEFAULT_RAW_DATA_DIR)

    log_file_path = trial.get_new_log_file(
        base_dir=user_cfg.RawDataDir,
        unit_serial=user_cfg.unitRef,
    )
    log_q_listener = logging.get_log_queue_listener()
    if log_q_listener is not None:
        logger.verbose("adding file handler to %s", log_file_path)
        log_q_listener.add_file_handler(
            log_file_path,
            formatter=logging.PreciseTimeFormatter(
                logging.MULTIPROC_LOG_FORMAT,
                datefmt=logging.DateTimeFormats.hour_time_precise,
                time_precision=3,
            ),
        )

    rc = -1
    try:
        if user_cfg_data is None:
            # logger.error("Exiting given config load failed.")
            return 1

        rcp_context = RcpRunContext(
            config_dir=cfg_dir,
            user_config=user_cfg,
            tasks_config=tasks_cfg_data[0],
        )

        app = App(rcp_context=rcp_context)
        logger.info("Running main loop..")
        rc = app.MainLoop()
        logger.verbose("app main loop returned %s", rc)
        return rc
    except KeyboardInterrupt:
        logger.notice("interrupted by user / keyboard interrupt from:", exc_info=True)
        rc = 1
    except SystemExit as err:
        logger.notice("interrupted by system exit from:", exc_info=True)
        rc = err.code or 1
    except BaseException as err:
        logger.exception("Fatal error: %s", err)
        rc = 255
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
