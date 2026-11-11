import platform

import pytest

from rcp_task_acquisition.utils.process import set_high_prio


def test_set_high_prio(caplog):
    if platform.system() == "Windows":
        set_high_prio()
        assert "Successfully set current process to high prio" in caplog.text
    else:
        with pytest.warns(UserWarning, match="not implemented"):
            set_high_prio()
