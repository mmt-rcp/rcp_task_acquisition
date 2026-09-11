import sys
from pathlib import Path

import matplotlib
import wx


# set up matplotlib to be compatible on commandline/spyder
matplotlib.use("qtagg")


def run_app():
    # delayed import on purpose.
    from rcp_task_acquisition.utils.repo import check_repo_up_to_date

    app = wx.App()

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

    from rcp_task_acquisition.panels.SwitchPanel import SwitchPanel  # noqa

    SwitchPanel()
    return app.MainLoop()


if __name__ == "__main__":
    sys.exit(run_app())
