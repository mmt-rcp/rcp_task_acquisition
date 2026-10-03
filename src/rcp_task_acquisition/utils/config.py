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


ItemConfigType = typing.TypeVar("ItemConfigType")
ItemsEnumType = typing.TypeVar("ItemsEnumType")


class DictConfig(dict[str, ItemConfigType], typing.Generic[ItemConfigType, ItemsEnumType]):
    item_cls: typing.Type[ItemConfigType]
    enum_cls: typing.Type[ItemsEnumType] | None

    def __new__(cls, arg0=None, **kwargs):
        dct = {}
        if arg0 is not None:
            if isinstance(arg0, typing.Mapping):
                kwargs.update(arg0)
            else:
                kwargs.update((k, v) for k, v in arg0)
        _load_enum_to_dct_class_items(kwargs, dct, cls.item_cls, cls.enum_cls)  # noqa
        self = super().__new__(cls)
        self.update(dct)
        return self

    def __init__(self, *args, **kwargs):
        super().__init__()

    def fill_defaults(self):
        enum_cls = self.enum_cls
        if enum_cls is None:
            return
        for member in enum_cls:
            if member not in self:
                self[member] = self.item_cls()

    @staticmethod
    def make_accessor(em) -> ItemConfigType:
        def wrapped(self) -> ItemConfigType:
            return self[em]

        return property(wrapped)  # noqa


def _load_enum_to_dct_class_items(
    dct,
    target_items,
    target_cls,
    enum_items,
    *,
    fill_default: bool = False,
):
    empty = {}
    if enum_items is not None:
        for member in enum_items:
            prev = target_items.get(member, None)
            sub = dct.pop(member.value, None)
            if prev is not None and sub is not None:
                raise ValueError(f"{member.value} provided via both items dict and kwargs")
            if sub is None and not fill_default:
                continue
            target_items[member] = (
                sub if isinstance(sub, target_cls) else target_cls(**(sub or empty))
            )
    else:
        for k, v in dct.items():
            target_items[k] = v if isinstance(v, target_cls) else target_cls(**(v or empty))
        dct.clear()


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

    def __post_init__(self):
        self.crop = tuple(self.crop)


@dataclasses.dataclass(kw_only=True)
class HardwareItemConfig:
    # name: str = ""
    labjack_input: str = ""
    voltage_range: tuple[float, float] = (0, 0)
    graph: str = ""

    def __post_init__(self):
        self.voltage_range = tuple(self.voltage_range)


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


class HardwareDictConfig(DictConfig[HardwareItemConfig, HardwareItem]):
    item_cls = HardwareItemConfig
    enum_cls = HardwareItem

    @staticmethod
    def _make_accessor(member) -> item_cls:
        return DictConfig.make_accessor(member)

    photo_detector = _make_accessor(HardwareItem.PHOTO_DETECTOR)
    subject_mic = _make_accessor(HardwareItem.SUBJECT_MIC)
    experimenter_mic = _make_accessor(HardwareItem.EXPERIMENTER_MIC)
    pc_audio = _make_accessor(HardwareItem.PC_AUDIO)
    grip_force_sensor = _make_accessor(HardwareItem.GRIP_FORCE_SENSOR)
    force_sensor_x = _make_accessor(HardwareItem.FORCE_SENSOR_X)
    force_sensor_y = _make_accessor(HardwareItem.FORCE_SENSOR_Y)
    force_sensor_z = _make_accessor(HardwareItem.FORCE_SENSOR_Z)
    camera_sync_ttl = _make_accessor(HardwareItem.CAMERA_SYNC_TTL)
    grasp_start_pad = _make_accessor(HardwareItem.GRASP_START_PAD)
    extra_digital_1 = _make_accessor(HardwareItem.EXTRA_DIGITAL_1)
    extra_digital_2 = _make_accessor(HardwareItem.EXTRA_DIGITAL_2)
    slow_barcode = _make_accessor(HardwareItem.SLOW_BARCODE)
    return_from_ds7a = _make_accessor(HardwareItem.RETURN_FROM_DS7A)
    trigger_to_ds7a = _make_accessor(HardwareItem.TRIGGER_TO_DS7A)
    ttl_to_ephys = _make_accessor(HardwareItem.TTL_TO_EPHYS)
    digital_accessory = _make_accessor(HardwareItem.DIGITAL_ACCESSORY)
    del _make_accessor  # only needed during class creation.


class CameraItem(str, enum.Enum):
    LEFT_CAM_TOP = "leftCamTop"
    RIGHT_CAM_TOP = "rightCamTop"
    LEFT_CAM_FACE = "leftCamFace"
    RIGHT_CAM_FACE = "rightCamFace"
    LEFT_CAM_TRIPOD = "leftCamTripod"
    RIGHT_CAM_TRIPOD = "rightCamTripod"


class CamerasDictConfig(DictConfig[CameraConfig, CameraItem]):
    """Dict subclass with some helper properties accessor, and automatic handling to CameraConfig"""

    item_cls = CameraConfig
    enum_cls = CameraItem

    @staticmethod
    def _make_accessor(member) -> item_cls:
        return DictConfig.make_accessor(member)

    left_cam_top = _make_accessor(CameraItem.LEFT_CAM_TOP)
    right_cam_top = _make_accessor(CameraItem.RIGHT_CAM_TOP)
    left_cam_tripod = _make_accessor(CameraItem.LEFT_CAM_TRIPOD)
    right_cam_tripod = _make_accessor(CameraItem.RIGHT_CAM_TRIPOD)
    left_cam_face = _make_accessor(CameraItem.LEFT_CAM_FACE)
    right_cam_face = _make_accessor(CameraItem.RIGHT_CAM_FACE)

    del _make_accessor  # only needed during class creation.


@dataclasses.dataclass(kw_only=True)
class _RcpUserConfig:
    unitRef: str = ""
    RawDataDir: str = ""
    VideoDir: str = ""
    cam_config: CamConfig = dataclasses.field(default_factory=CamConfig)
    cameras: CamerasDictConfig = dataclasses.field(default_factory=CamerasDictConfig)
    hardware: HardwareDictConfig = dataclasses.field(default_factory=HardwareDictConfig)


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
                CamerasDictConfig: lambda v: CamerasDictConfig(**v),
                HardwareDictConfig: lambda v: HardwareDictConfig(**v),
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


class RcpTasksConfig(DictConfig[RcpTaskConfig, None]):
    item_cls = RcpTaskConfig
    enum_cls = None


@dataclasses.dataclass(kw_only=True)
class RcpTasksConfigWrapper:
    tasks: RcpTasksConfig = dataclasses.field(default_factory=RcpTasksConfig)


def load_rcp_tasks_config(file_path: Path | None = None) -> tuple[Path, RcpTasksConfig]:
    if file_path is None:
        file_path = Path(constants.CONFIG_FILE_PATH, "taskconfig.yaml")
    with file_path.open() as fh:
        cfg = load_rcp_tasks_config_buffer(fh)
    return file_path, cfg


def load_rcp_tasks_config_buffer(buffer: typing.TextIO) -> RcpTasksConfig:
    loader = yaml.SafeLoader
    dct = yaml.load(buffer, Loader=loader)

    def gen_tasks_config(v):
        return RcpTasksConfig(**v)

    cfg = dacite.from_dict(
        RcpTasksConfigWrapper,
        {"tasks": dct},
        config=dacite.Config(
            type_hooks={
                RcpTasksConfig: gen_tasks_config,
                RcpTaskConfig: lambda v: RcpTaskConfig(**v),
            },
            check_types=False,
        ),
    )
    return cfg.tasks


def load_rcp_config(config_dir: Path | None = None):
    if config_dir is None:
        config_dir = Path(constants.STIM_CONFIG_FILE_PATH)
    user_cfg_path, user_cfg = load_rcp_user_config(config_dir.joinpath("userdata.yaml"))
    task_cfg_path, tasks_cfg = load_rcp_tasks_config(config_dir.joinpath("taskconfig.yaml"))
    return user_cfg_path, user_cfg, task_cfg_path, tasks_cfg


#
# def represent_cameras_dict_config(dumper: "RcpConfigYamlDumper", data: CamerasDictConfig) -> Node:
#     dct = dict(data)
#     node = dumper.represent_dict(dct)
#     return node
#
#
# class RcpConfigYamlDumper(
#     # yaml.SafeDumper
#     ruamel.yaml.SafeDumper,
# ):
#
#     yaml_representers = {
#         CamerasDictConfig: represent_cameras_dict_config
#     }
#
#
# def dataclass_representer(dumper: RcpConfigYamlDumper, obj):
#     dct = {
#         field.name: getattr(obj, field.name)
#         for field in dataclasses.fields(obj)
#     }
#     # node = dumper.represent_mapping("", dct)
#     # node = dumper.represent_dict(dct)
#     # node.tag = ""
#     return dumper.represent_dict(dct)
#
#
# # RcpConfigYamlDumper.add_representer(CameraItem, RcpConfigYamlDumper.represent_str)
# # RcpConfigYamlDumper.add_representer(
# #     HardwareItemConfig, RcpConfigYamlDumper.represent_str
# # )
#
# for _cls in (RcpUserConfig, HardwareItemConfig, CameraConfig):
#     RcpConfigYamlDumper.add_representer(_cls, dataclass_representer)

##


def to_raw_recursive(obj: typing.Any):
    if isinstance(obj, enum.Enum):
        return obj.value
    if isinstance(obj, str):
        return obj
    if isinstance(obj, (list, typing.Sequence)):
        return obj.__class__(to_raw_recursive(v) for v in obj)
    if isinstance(obj, (dict, typing.Mapping)):
        return {to_raw_recursive(k): to_raw_recursive(v) for k, v in obj.items()}  # noqa
    if dataclasses.is_dataclass(obj):
        return {f.name: to_raw_recursive(getattr(obj, f.name)) for f in dataclasses.fields(obj)}
    return obj


def save_rcp_user_config_buffer(config: RcpUserConfig, buffer: typing.TextIO) -> None:
    # dumper = RcpConfigYamlDumper
    # dct = dataclasses.asdict(config)
    dct = to_raw_recursive(config)
    yaml.safe_dump(
        dct,
        buffer,
        sort_keys=False,  # rely on dataclasses fields order
    )
    # yaml.dump_all([config], buffer, Dumper=dumper, default_flow_style=False)
    # dumper = RcpConfigYamlDumper(buffer)
    # ruamel.yaml.YAML()
    # ruamel.yaml.safe_dump(config, buffer, Dumper=dumper,
    #           # default_flow_style=False
    #           )


def save_rcp_user_config(config: RcpUserConfig, file_path: Path) -> None:
    with file_path.open("w") as fh:
        save_rcp_user_config_buffer(config, fh)


def save_rcp_tasks_config_buffer(config: RcpTasksConfig, buffer: typing.TextIO) -> None:
    dct = to_raw_recursive(config)
    yaml.safe_dump(
        dct,
        buffer,
        sort_keys=False,  # rely on dataclasses fields order
    )


def save_rcp_tasks_config(config: RcpTasksConfig, file_path: Path) -> None:
    with file_path.open("w") as fh:
        save_rcp_tasks_config_buffer(config, fh)
