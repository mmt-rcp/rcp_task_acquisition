import dataclasses
import enum
import typing
from pathlib import Path
from types import GenericAlias
from typing import Any

import yaml

import ruamel.yaml.comments
from ruamel.yaml.comments import CommentedMap

import dacite

from rcp_task_acquisition.utils import constants
from rcp_task_acquisition.utils.logging import get_verbose_logger

logger = get_verbose_logger(__name__)

DictKeyType = typing.TypeVar("DictKeyType", bound=str)
DictDataType = typing.TypeVar("DictDataType")
ItemsEnumType = typing.TypeVar("ItemsEnumType")


class DictConfig(dict[DictKeyType, DictDataType], typing.Generic[DictKeyType, DictDataType]):
    enum_cls: type[DictKeyType]
    item_cls: type[DictDataType]

    def __new__(cls, arg0=None, **kwargs):
        if arg0 is not None and len(kwargs) > 0:
            raise TypeError("Do not support both arg and kwargs")
        dct = {}
        if arg0 is not None:
            kwargs.update(arg0)
        _load_enum_to_dct_class_items(kwargs, dct, cls.item_cls, cls.enum_cls)  # noqa
        if len(kwargs) > 0:
            raise ValueError(f"Unhandled key(s): {tuple(kwargs)}")
        self = super().__new__(cls)
        self.update(dct)
        return self

    def __init__(self, *args, **kwargs):
        del args, kwargs  # initialized in __new__
        super().__init__()  # still call for good practice, but with none args/kwargs

    def __getitem__(self, item: str | DictKeyType) -> DictDataType:
        e_cls = self.enum_cls
        if not isinstance(item, e_cls):
            item = e_cls(item)
        return super().__getitem__(item)

    def __setitem__(self, item: str | DictKeyType, value: DictDataType):
        e_cls = self.enum_cls
        if not isinstance(item, e_cls):
            item = e_cls(item)
        super().__setitem__(item, value)

    def fill_defaults(self):
        enum_cls = self.enum_cls
        if enum_cls is None:
            return
        for member in enum_cls:
            if member not in self:
                self[member] = self.item_cls()

    @staticmethod
    def make_accessor(em):
        def wrapped(self) -> DictDataType:
            try:
                return self[em]
            except KeyError:
                logger.verbose("created item %s on attribute access")
                item = self[em] = self.item_cls()
                return item

        return property(wrapped)


def _load_enum_to_dct_class_items(
    dct,
    target_items,
    target_cls,
    enum_items,
    *,
    fill_default: bool = False,
):
    empty: dict[str, typing.Any] = {}
    if issubclass(enum_items, enum.Enum):
        for member in enum_items:
            sub = dct.pop(member.value, None)
            if sub is None and not fill_default:
                continue
            target_items[member] = (
                sub if isinstance(sub, target_cls) else target_cls(**(sub or empty))
            )
    else:
        target_items.update(
            (k, v if isinstance(v, target_cls) else target_cls(**(v or empty)))
            for k, v in dct.items()
        )
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
    bin: int = 1
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
    TTL_TO_E_PHYS = "TTL to E-Phys"
    DIGITAL_ACCESSORY = "Digital Accessory"


class HardwareDictConfig(DictConfig[HardwareItem, HardwareItemConfig]):
    item_cls = HardwareItemConfig
    enum_cls = HardwareItem

    @staticmethod
    def _make_accessor(member) -> HardwareItemConfig:
        return DictConfig.make_accessor(member)  # noqa

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
    ttl_to_e_phys = _make_accessor(HardwareItem.TTL_TO_E_PHYS)
    digital_accessory = _make_accessor(HardwareItem.DIGITAL_ACCESSORY)
    del _make_accessor  # only needed during class creation.


class CameraItem(str, enum.Enum):
    LEFT_CAM_TOP = "leftCamTop"
    RIGHT_CAM_TOP = "rightCamTop"
    LEFT_CAM_FACE = "leftCamFace"
    RIGHT_CAM_FACE = "rightCamFace"
    LEFT_CAM_TRIPOD = "leftCamTripod"
    RIGHT_CAM_TRIPOD = "rightCamTripod"


class CamerasDictConfig(DictConfig[CameraItem, CameraConfig]):
    """Dict subclass with some helper properties accessor, and automatic handling to CameraConfig"""

    item_cls = CameraConfig
    enum_cls = CameraItem

    @staticmethod
    def _make_accessor(member) -> CameraConfig:
        return DictConfig.make_accessor(member)  # noqa

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


def load_rcp_user_config(file_path) -> tuple[RcpUserConfig, CommentedMap]:
    with file_path.open() as fh:
        cfg, commented_cfg = load_rcp_user_config_buffer(fh)
    return cfg, commented_cfg


def load_rcp_user_config_buffer(buffer, *, strict_only=True) -> tuple[RcpUserConfig, CommentedMap]:
    loader = ruamel.yaml.YAML(typ="rt")
    commented_config: CommentedMap = loader.load(buffer)
    buffer.seek(0)
    # NB: ruamel.yaml allows to have the comments handled. but the returned "dict"(-kind) instance,
    # and basically all inner values, are "Commented" maps/sequences...
    # and not succeeding to get raw values for now from that.
    # Preferring to have pure Python types (dict/list/tuples/etc..) instead.
    loader = yaml.SafeLoader

    dct = yaml.load(buffer, Loader=loader)

    def _load(*, strict):
        return dacite.from_dict(
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
                check_types=strict,
                strict=strict,
            ),
        )

    try:
        cfg = _load(strict=True)
    except Exception as err:
        if strict_only:
            cfg = None
        else:
            try:
                cfg = _load(strict=False)
            except Exception:  # noqa
                cfg = None
        if cfg is None:
            raise err
        logger.warning("failed load with strict mode but succeeded without. strict error: %s", err)

    return cfg, commented_config


###


@dataclasses.dataclass(kw_only=True)
class RcpTaskConfig:
    settings: list[str] = dataclasses.field(default_factory=list)


class RcpTasksGroupConfig(DictConfig[str, RcpTaskConfig]):
    item_cls = RcpTaskConfig
    enum_cls = str


@dataclasses.dataclass(kw_only=True)
class RcpTasksConfigWrapper:
    tasks: RcpTasksGroupConfig = dataclasses.field(default_factory=RcpTasksGroupConfig)


def load_rcp_tasks_config(
    file_path: Path,
) -> tuple[RcpTasksGroupConfig, CommentedMap]:
    with file_path.open() as fh:
        cfg, commented_cfg = load_rcp_tasks_config_buffer(fh)
    return cfg, commented_cfg


def load_rcp_tasks_config_buffer(buffer: typing.TextIO) -> tuple[RcpTasksGroupConfig, CommentedMap]:
    loader = ruamel.yaml.YAML(pure=True, typ="rt")
    commented_config = loader.load(buffer)
    buffer.seek(0)

    loader = yaml.SafeLoader
    dct = yaml.load(buffer, Loader=loader)

    def gen_tasks_config(v):
        return RcpTasksGroupConfig(**v)

    cfg = dacite.from_dict(
        RcpTasksConfigWrapper,
        {"tasks": dct},
        config=dacite.Config(
            type_hooks={
                RcpTasksGroupConfig: gen_tasks_config,
                RcpTaskConfig: lambda v: RcpTaskConfig(**v),
                CamerasDictConfig: lambda v: CamerasDictConfig(**v),
            },
            check_types=False,
        ),
    )
    return cfg.tasks, commented_config


def load_rcp_config(config_dir: Path):
    user_data = load_rcp_user_config(config_dir.joinpath("userdata.yaml"))
    tasks_data = load_rcp_tasks_config(config_dir.joinpath("taskconfig.yaml"))
    return user_data, tasks_data


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
    if isinstance(obj, (list, tuple)):
        return obj.__class__(to_raw_recursive(v) for v in obj)
    if isinstance(obj, (dict, typing.Mapping)):
        return {to_raw_recursive(k): to_raw_recursive(v) for k, v in obj.items()}
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


def save_rcp_tasks_config_buffer(config: RcpTasksGroupConfig, buffer: typing.TextIO) -> None:
    dct = to_raw_recursive(config)
    yaml.safe_dump(
        dct,
        buffer,
        sort_keys=False,  # rely on dataclasses fields order
    )


def save_rcp_tasks_config(config: RcpTasksGroupConfig, file_path: Path) -> None:
    with file_path.open("w") as fh:
        save_rcp_tasks_config_buffer(config, fh)


def update_commented_config(config: RcpUserConfig | RcpTasksGroupConfig, commented: CommentedMap):
    pass
    # eventual todo: try use with save functions,
    #  given it's not necessarily always easy and/or possible
