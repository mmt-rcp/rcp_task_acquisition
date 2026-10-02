import platform

import pytest

from rcp_task_acquisition.utils.process import set_high_prio


@pytest.mark.xfail(condition=platform.system() != "Windows", reason="Windows only")
def test_set_high_prio(caplog):
    set_high_prio()
    assert "Successfully set current process to high prio" in caplog.text
