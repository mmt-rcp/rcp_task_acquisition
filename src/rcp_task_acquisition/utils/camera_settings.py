import multiprocessing
from dataclasses import dataclass

import cv2
import numpy as np

from rcp_task_acquisition.utils.config import CameraConfig, CameraItem
from rcp_task_acquisition.utils.typing import SharedArray, SharedInt, FrameDimsTupleT


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
    frame_dims: FrameDimsTupleT
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

    def put_to(self, data, *, timeout=3):
        self.camq.put(data, timeout=timeout)

    def get_from(self, *, timeout=3):
        return self.camq_p2read.get(timeout=timeout)

    def apply_new_dims(self, new_dims: FrameDims):
        frame = self.frameBuff[0 : new_dims.dispSize].reshape([new_dims.h, new_dims.w, 3])
        frame = cv2.cvtColor(frame, cv2.COLOR_BGR2RGB)
        for f in range(3):
            self.frame[new_dims.y1 : new_dims.y2, new_dims.x1 : new_dims.x2, f] = frame[:, :, f]
        self.frame_size = new_dims
