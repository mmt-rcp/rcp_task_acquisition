# set up matplotlib to be compatible on commandline/spyder
import matplotlib
import wx

from rcp_task_acquisition.utils import config
from rcp_task_acquisition.utils.run_context import RcpRunContext

matplotlib.use("qtagg")

from rcp_task_acquisition.panels.SwitchPanel import SwitchPanel


def run_app():
    app = wx.App()
    user_cfg_path, user_cfg, task_cfg_path, tasks_cfg = config.load_rcp_config()
    rcp_context = RcpRunContext(
        config_file_path=user_cfg_path,
        user_config=user_cfg,
        tasks_config=tasks_cfg,
    )
    SwitchPanel(rcp_context=rcp_context)
    app.MainLoop()


if __name__ == "__main__":
    run_app()
