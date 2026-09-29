import io
from pathlib import Path

import pytest

from rcp_task_acquisition.utils import constants, config
from rcp_task_acquisition.utils.config import RcpUserConfig
from rcp_task_acquisition.utils.run_context import RcpRunContext


@pytest.fixture
def rcp_run_ctx():
    ctx = RcpRunContext(
        config_file_path=constants.DEFAULT_USER_CONFIG_PATH,
        config=RcpUserConfig(),
    )
    yield ctx


def test_default_base_dir(rcp_run_ctx):
    assert rcp_run_ctx.base_dir == constants.BASEDIR


def test_load_default():
    effective_path, cfg = config.load_rcp_user_config()
    assert isinstance(effective_path, Path)
    assert isinstance(cfg, RcpUserConfig)
    assert isinstance(cfg.cam_config, config.CamConfig)


def test_load_buffer():
    buffer = io.StringIO(
        """
cameras:
    leftCamTop:
        serial: '23531686'
        ismaster: false
        crop:
        - 90
        - 540
        - 0
        - 540
        exposure: 1000
        bin: 1
        gain: 15
        gamma: 0.333
        framerate_decrease_factor: 2
        flip: false
        in_use: true
"""
    )
    cfg = config.load_rcp_user_config_buffer(buffer)
    assert isinstance(cfg, RcpUserConfig)
    assert len(cfg.cameras) == 1
    assert "leftCamTop" in cfg.cameras
    cam = cfg.cameras["leftCamTop"]
    assert cam.gamma == 0.333
    assert cam.crop == [90, 540, 0, 540]
    assert len(cfg.hardware) == 0
    assert cfg.unitRef == ""
    # etc...
