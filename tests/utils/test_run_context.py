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


def test_load_save_buffer():
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
    assert len(cfg.cameras) == 6
    assert "leftCamTop" in cfg.cameras
    left_cam_top = cfg.cameras["leftCamTop"]
    assert cfg.cameras.left_cam_top is left_cam_top
    assert left_cam_top.gamma == 0.333
    assert left_cam_top.crop == [90, 540, 0, 540]
    assert len(cfg.hardware) == 0
    assert cfg.unitRef == ""
    # etc...
    buffer = io.StringIO()
    config.save_rcp_user_config_buffer(cfg, buffer)
    print(buffer.getvalue())
