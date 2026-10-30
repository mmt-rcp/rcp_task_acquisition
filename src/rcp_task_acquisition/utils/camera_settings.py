import multiprocessing
from dataclasses import dataclass

import numpy as np

from rcp_task_acquisition.utils.config import CameraConfig, CameraItem
from rcp_task_acquisition.utils.typing import SharedArray, SharedInt


@dataclass
class FrameDims:
    x1: int = 0
    x2: int = 0
    y1: int = 0
    y2: int = 0
    h: int = 0
    w: int = 0
    dispSize: int = 0


@dataclass
class CamSettings:
    idx: int  # cam index
    name: str
    cam_item: CameraItem
    serial: str
    is_primary: bool
    size: int
    shape: list[int]
    bin_val: int
    frame_dims: list[int]
    decrease_val: int
    actual_framerate: float
    exposure: None | float
    cam_tests: np.ndarray
    contrast_tests: np.ndarray
    frame: np.ndarray
    frameBuff: np.ndarray
    array4feed: SharedArray
    frmGrab: SharedInt
    camq: multiprocessing.Queue
    camq_p2read: multiprocessing.Queue
    frame_size: FrameDims
    base_config: CameraConfig
