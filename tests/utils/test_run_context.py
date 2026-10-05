import io
import os
from pathlib import Path

import pytest

from rcp_task_acquisition.utils import constants, config
from rcp_task_acquisition.utils.config import RcpUserConfig
from rcp_task_acquisition.utils.run_context import RcpRunContext


@pytest.fixture
def rcp_run_ctx():
    ctx = RcpRunContext(
        config_file_path=constants.DEFAULT_USER_CONFIG_PATH,
        user_config=config.RcpUserConfig(),
        tasks_config=config.RcpTasksConfig(),
    )
    yield ctx


def test_default_base_dir(rcp_run_ctx):
    assert rcp_run_ctx.base_dir == constants.BASEDIR


def test_load_default():
    effective_path, cfg, _ = config.load_rcp_user_config()
    assert isinstance(effective_path, Path)
    assert isinstance(cfg, RcpUserConfig)
    assert isinstance(cfg.hardware, config.HardwareDictConfig)
    assert isinstance(cfg.cameras, config.CamerasDictConfig)
    assert isinstance(cfg.cam_config, config.CamConfig)


def test_load_save_buffer():
    serial = f"23531686{os.getpid()}"
    buffer = io.StringIO(
        f"""
cameras:
    leftCamTop:
        serial: '{serial}'
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
    cfg, _ = config.load_rcp_user_config_buffer(buffer)
    assert isinstance(cfg, RcpUserConfig)
    assert len(cfg.cameras) == 1
    assert "leftCamTop" in cfg.cameras
    left_cam_top = cfg.cameras["leftCamTop"]
    assert cfg.cameras.left_cam_top is left_cam_top
    assert left_cam_top.gamma == 0.333
    assert left_cam_top.crop == (90, 540, 0, 540)
    assert len(cfg.hardware) == 0
    assert cfg.unitRef == ""
    # etc...
    buffer = io.StringIO()
    config.save_rcp_user_config_buffer(cfg, buffer)
    out = buffer.getvalue()
    assert f"serial: '{serial}'" in out
    buffer.seek(0)
    cfg2, _ = config.load_rcp_user_config_buffer(buffer)
    assert cfg == cfg2
    #


def test_auto_generate_on_attribute_access(rcp_run_ctx):
    def to_attr_name(v):
        return v.lower().replace(" ", "_").replace("-", "_")

    hardware = rcp_run_ctx.user_config.hardware
    for hard_item in config.HardwareItem:
        assert hard_item not in hardware
        hard = getattr(hardware, to_attr_name(hard_item.name))
        assert hard_item in hardware
        assert hard is hardware[hard_item]
    #
    cameras = rcp_run_ctx.user_config.cameras
    for cam_item in config.CameraItem:
        assert cam_item not in cameras
        cam = getattr(cameras, to_attr_name(cam_item.name))
        assert cam_item in cameras
        assert cam is cameras[cam_item]


def test_load_save_default(rcp_run_ctx):
    cfg = rcp_run_ctx.user_config
    cfg.hardware.fill_defaults()
    cfg.cameras.fill_defaults()
    buffer = io.StringIO()
    config.save_rcp_user_config_buffer(cfg, buffer)
    buffer.seek(0)
    cfg2, _ = config.load_rcp_user_config_buffer(buffer)
    assert cfg == cfg2


def test_fill_defaults(rcp_run_ctx):
    cfg = rcp_run_ctx.user_config
    assert cfg.cameras == {}
    assert cfg.hardware == {}
    cfg.cameras.fill_defaults()
    assert len(cfg.cameras) == len(list(cfg.cameras.enum_cls))
    cfg.hardware.fill_defaults()
    assert len(cfg.hardware) == len(list(cfg.hardware.enum_cls))


def test_accessor(rcp_run_ctx):
    cfg = rcp_run_ctx.user_config
    cams = cfg.cameras
    cams.fill_defaults()
    assert cams.left_cam_top is cams[cams.enum_cls.LEFT_CAM_TOP]  # one explicit example
    # ensure all of them:
    for m in cams.enum_cls:
        assert getattr(cams, m.name.lower()) is cams[m]
    # some for hardware:
    hard = cfg.hardware
    hard.fill_defaults()
    assert hard.photo_detector is hard[hard.enum_cls.PHOTO_DETECTOR]
    assert hard.experimenter_mic is hard[hard.enum_cls.EXPERIMENTER_MIC]
    # etc.. :
    for m in hard.enum_cls:
        assert getattr(hard, m.name.lower()) is hard[m]


def test_tasks_config():
    buffer = io.StringIO("""
first task with space:  # comment1
  settings:
  - Photodetector
  - Subject Mic
n_back:
  settings:
  - Photodetector
  - Subject Mic
  - Experimenter Mic
  """)
    cfg, commented_cfg = config.load_rcp_tasks_config_buffer(buffer)
    assert len(cfg) == 2
    assert tuple(cfg) == ("first task with space", "n_back")
    n_back = cfg["n_back"]
    assert isinstance(n_back, config.RcpTaskConfig)
    assert len(n_back.settings) == 3
    cfg["another"] = config.RcpTaskConfig(settings=["foobar"])
    buffer = io.StringIO()
    config.save_rcp_tasks_config_buffer(cfg, buffer)
    out = buffer.getvalue()
    # print(out)
    # assert "another" in out
    buffer.seek(0)
    cfg2, _ = config.load_rcp_tasks_config_buffer(buffer)
    assert cfg2["another"].settings == ["foobar"]
    assert cfg == cfg2
    cfg.pop("another")
    assert cfg != cfg2
