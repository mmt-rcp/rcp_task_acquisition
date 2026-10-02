import typing
from pathlib import Path

import dataclasses
import enum
from typing import Callable

import dacite
import ruamel.yaml
import ruamel.yaml.util
import yaml
from yaml import Node as Node

from rcp_task_acquisition.utils import constants


def _load_enum_to_dct_class_items(dct, target_items, target_cls, enum_items):
    empty = {}
    for member in enum_items:
        prev = target_items.get(member, None)
        sub = dct.pop(member.value, None)
        if prev is not None and sub is not None:
            raise ValueError(f"{member.value} provided via both items dict and kwargs")
        target_items[member] = sub if isinstance(sub, target_cls) else target_cls(**(sub or empty))


@dataclasses.dataclass(kw_only=True)
class CamConfig:
    framerate: float = 240
    framerate_decrease_factor: float = 2
    is_unconnected: bool = False


@dataclasses.dataclass(kw_only=True)
class CameraConfig:
    serial: str = ""
    ismaster: bool = False
    crop: tuple[int, int, int, int] = (0, 0, 0, 0)
    exposure: float | None = None
    bin: int | None = None
    gain: float | None = None
    gamma: float | None = None
    framerate_decrease_factor: float = 1
    flip: bool = False
    in_use: bool = True


@dataclasses.dataclass(kw_only=True)
class HardwareItemConfig:
    # name: str = ""
    labjack_input: str = ""
    voltage_range: tuple[float, float] = (0, 0)
    graph: str = ""


class HardwareItem(str, enum.Enum):
    PHOTO_DETECTOR = "Photodetector"
    SUBJECT_MIC = "Subject Mic"
    EXPERIMENTER_MIC = "Experimenter Mic"
    PC_AUDIO = "PC Audio"
    GRIP_FORCE_SENSOR = "Grip Force Sensor"
    FORCE_SENSOR_X = "Force Sensor X"
    FORCE_SENSOR_Y = "Force Sensor Y"
    FORCE_SENSOR_Z = "Force Sensor Z"
    CAMERA_SYNC_TTL = "Camera Sync TTL"
    GRASP_START_PAD = "Grasp Start Pad"
    EXTRA_DIGITAL_1 = "Extra Digital In 1"
    EXTRA_DIGITAL_2 = "Extra Digital In 2"
    SLOW_BARCODE = "Slow Barcode"
    RETURN_FROM_DS7A = "Return From DS7A"
    TRIGGER_TO_DS7A = "Trigger to DS7A"
    TTL_TO_EPHYS = "TTL to E-Phys"
    DIGITAL_ACCESSORY = "Digital Accessory"


@dataclasses.dataclass(kw_only=True)
class _HardwareConfig:
    items: dict[str, HardwareItemConfig] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(kw_only=True)
class HardwareConfig(_HardwareConfig):
    def __init__(self, *, items: dict | None = None, **kwargs):
        items = {} if items is None else items
        _load_enum_to_dct_class_items(kwargs, items, HardwareItemConfig, HardwareItem)
        super().__init__(items=items, **kwargs)

    @staticmethod
    def _make_accessor(v):
        def wrapped(self) -> HardwareItemConfig:
            return self.items[v]

        return property(wrapped)

    photo_detector = _make_accessor(HardwareItem.PHOTO_DETECTOR)
    subject_mic = _make_accessor(HardwareItem.SUBJECT_MIC)
    pc_audio = _make_accessor(HardwareItem.PC_AUDIO)
    digital_accessory = _make_accessor(HardwareItem.DIGITAL_ACCESSORY)
    force_sensor_x = _make_accessor(HardwareItem.FORCE_SENSOR_X)
    force_sensor_y = _make_accessor(HardwareItem.FORCE_SENSOR_Y)
    force_sensor_z = _make_accessor(HardwareItem.FORCE_SENSOR_Z)
    # etc...

    del _make_accessor  # only needed during class creation.


class CameraItem(str, enum.Enum):
    LEFT_CAM_TOP = "leftCamTop"
    RIGHT_CAM_TOP = "rightCamTop"
    LEFT_CAM_FACE = "leftCamFace"
    RIGHT_CAM_FACE = "rightCamFace"
    LEFT_CAM_TRIPOD = "leftCamTripod"
    RIGHT_CAM_TRIPOD = "rightCamTripod"


@dataclasses.dataclass(kw_only=True)
class _CamerasConfig:
    items: dict[str, CameraConfig] = dataclasses.field(default_factory=dict)


class CamerasDictConfig(dict[str, CameraConfig]):
    """Dict subclass with some helper properties accessor, and automatic handling to CameraConfig"""

    def __new__(cls, arg0=None, **kwargs):
        items = {}
        if arg0 is not None:
            kwargs.update((k, v) for k, v in arg0)
        _load_enum_to_dct_class_items(kwargs, items, CameraConfig, CameraItem)
        self = super().__new__(cls)
        # super().__init__()
        self.update(items)
        return self

    def __init__(self, *args, **kwargs):
        super().__init__()

    @staticmethod
    def _make_accessor(em) -> CameraConfig:
        def wrapped(self) -> CameraConfig:
            return self[em]

        return property(wrapped)  # noqa

    left_cam_top = _make_accessor(CameraItem.LEFT_CAM_TOP)
    right_cam_top = _make_accessor(CameraItem.RIGHT_CAM_TOP)
    left_cam_tripod = _make_accessor(CameraItem.LEFT_CAM_TRIPOD)
    right_cam_tripod = _make_accessor(CameraItem.RIGHT_CAM_TRIPOD)
    left_cam_face = _make_accessor(CameraItem.LEFT_CAM_FACE)
    right_cam_face = _make_accessor(CameraItem.RIGHT_CAM_FACE)

    del _make_accessor  # only needed during class creation.


@dataclasses.dataclass(kw_only=True)
class _RcpUserConfig:
    cam_config: CamConfig = dataclasses.field(default_factory=CamConfig)
    unitRef: str = ""
    RawDataDir: str = ""
    VideoDir: str = ""
    cameras: CamerasDictConfig = dataclasses.field(default_factory=CamerasDictConfig)
    hardware: dict[str, HardwareItemConfig] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(kw_only=True)
class RcpUserConfig(_RcpUserConfig):
    pass
    # def __init__(self, **kwargs):  # for debug
    #     super().__init__(**kwargs)


def load_rcp_user_config(file_path: Path | None = None) -> tuple[Path, RcpUserConfig]:
    if file_path is None:
        file_path = constants.DEFAULT_USER_CONFIG_PATH
    with file_path.open() as fh:
        cfg = load_rcp_user_config_buffer(fh)
    return file_path, cfg


def load_rcp_user_config_buffer(buffer) -> RcpUserConfig:
    # loader = ruamel.yaml.YAML(pure=True)
    # dct = loader.load(buffer)
    # NB: ruamel.yaml allows to have the comments handled. but the returned "dict"(-kind) instance,
    # and basically all inner values, are "Commented" maps/sequences...
    # Preferring to have pure Python types (dict/list/tuples/etc..) instead.
    loader = yaml.SafeLoader
    dct = yaml.load(buffer, Loader=loader)
    cfg = dacite.from_dict(
        RcpUserConfig,
        dct,
        config=dacite.Config(
            type_hooks={
                CamerasDictConfig: lambda v: CamerasDictConfig(**v)
                # RcpConfig: lambda v: RcpConfig(**v),
                # CamerasConfig: lambda v: CamerasConfig(**dict(v)),
                # HardwareConfig: lambda v: HardwareConfig(**dict(v)),
                # ruamel.yaml.CommentedMap: lambda v: dict(v),
            },
            check_types=False,
        ),
    )
    return cfg


###


@dataclasses.dataclass(kw_only=True)
class RcpTaskConfig:
    settings: list[str] = dataclasses.field(default_factory=list)


@dataclasses.dataclass(kw_only=True)
class _RcpTasksConfig:
    items: dict[str, RcpTaskConfig] = dataclasses.field(default_factory=dict)


@dataclasses.dataclass(kw_only=True)
class RcpTasksConfig(RcpTaskConfig):
    pass
    # def __init__(self, *, items: dict | None = None, **kwargs):
    #     items = {} if items is None else items
    #     _load_dict(kwargs, items, RcpTaskConfig, HardwareItem)
    #     super().__init__(items=items, **kwargs)


def load_rcp_tasks_config(file_path: Path | None = None) -> tuple[Path, RcpTaskConfig]:
    if file_path is None:
        file_path = Path(constants.CONFIG_FILE_PATH, "taskconfig.yaml")
    with file_path.open() as fh:
        cfg = load_rcp_tasks_config_buffer(fh)
    return file_path, cfg


def load_rcp_tasks_config_buffer(buffer: typing.TextIO) -> RcpTasksConfig:
    loader = yaml.SafeLoader
    dct = yaml.load(buffer, Loader=loader)
    cfg = dacite.from_dict(
        RcpTasksConfig,
        dct,
        config=dacite.Config(
            type_hooks={},
            check_types=False,
        ),
    )
    return cfg


def load_rcp_config(config_dir: Path | None = None):
    if config_dir is None:
        config_dir = Path(constants.STIM_CONFIG_FILE_PATH)
    user_cfg_path, user_cfg = load_rcp_user_config(config_dir.joinpath("userdata.yaml"))
    task_cfg_path, tasks_cfg = load_rcp_tasks_config(config_dir.joinpath("taskconfig.yaml"))
    return user_cfg_path, user_cfg, task_cfg_path, tasks_cfg


def save_rcp_user_config(config: RcpUserConfig, file_path: Path) -> None:
    with file_path.open("w") as fh:
        save_rcp_user_config_buffer(config, fh)


class RcpConfigYamlDumper(yaml.SafeDumper):
    # tag = "!RcpConfigYamlDumper"

    def represent_cameras_dict_config(self, data: CamerasDictConfig) -> Node:
        return self.represent_dict({str(k): v for k, v in data.items()})

    yaml_representers = {CamerasDictConfig: represent_cameras_dict_config}


RcpConfigYamlDumper.add_representer(CameraItem, yaml.representer.SafeRepresenter.represent_str)
RcpConfigYamlDumper.add_representer(
    HardwareItemConfig, yaml.representer.SafeRepresenter.represent_str
)


def to_dict(obj: typing.Any):
    if isinstance(obj, (str, CamerasDictConfig)):
        return obj
    if isinstance(obj, (list, tuple, typing.Sequence)):
        return tuple(to_dict(v) for v in obj)
    elif isinstance(obj, (dict, typing.Mapping)):
        return {k: to_dict(v) for k, v in obj.items()}
    elif dataclasses.is_dataclass(obj):
        return {k: to_dict(v) for k, v in obj.__dict__.items()}
    return obj


def save_rcp_user_config_buffer(config: RcpUserConfig, buffer: typing.TextIO) -> None:
    dumper = RcpConfigYamlDumper
    # dct = dataclasses.asdict(config)
    dct = to_dict(config)
    yaml.dump(dct, buffer, dumper, default_flow_style=False)
