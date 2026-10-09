import matplotlib
import numpy as np
import wx
from matplotlib import patches

from rcp_task_acquisition.utils import config
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.typing import CropTupleType

logger = get_logger(__name__)


class Crop:
    def __init__(self):
        self.croprec: list[matplotlib.patches.Rectangle] = []
        self.croproi: list[CropTupleType] = []
        self.set_crop = None

    def set_key_crop(self, axes, keyCode) -> None:
        if self.cropAxes is None:
            return
        if keyCode == wx.WXK_LEFT:
            x = -1
            y = w = h = 0
        elif keyCode == wx.WXK_RIGHT:
            x = 1
            y = w = h = 0
        elif keyCode == wx.WXK_UP:
            x = w = h = 0
            y = -1
        elif keyCode == wx.WXK_DOWN:
            x = w = h = 0
            y = 1
        # Increase size
        elif keyCode == ord("A"):
            x = -2
            y = +2
            w = h = +4
        # Decrease size
        elif keyCode == ord("S"):
            x = +2
            y = -2
            w = h = -4
        else:
            logger.warning("set_key_crop: unhandled keycode: %s", keyCode)
            return

        ndx = axes.index(self.cropAxes)
        self.croproi[ndx][0] += x
        self.croproi[ndx][1] += w
        self.croproi[ndx][2] += y
        self.croproi[ndx][3] += h

    def create_crop(self, cam_cfg, cam_list, axes) -> None:
        ndx = axes.index(self.cropAxes)
        s = cam_list[ndx]
        cam_cfg[s]["crop"] = np.ndarray.tolist(self.croproi[ndx])

    def drawROI(self, axes) -> None:
        # if self.set_crop.GetValue():
        ndx = axes.index(self.cropAxes)
        self.croprec[ndx].set_x(self.croproi[ndx][0])
        self.croprec[ndx].set_y(self.croproi[ndx][2])
        self.croprec[ndx].set_width(self.croproi[ndx][1])
        self.croprec[ndx].set_height(self.croproi[ndx][3])
        # if not self.croproi[ndx][0] == 0:
        #     self.croprec[ndx].set_alpha(0.6)
        # self.figure.canvas.draw()

    def adjust_crop(self, event, axes, cam_list, cam_config: config.CamerasDictConfig) -> None:
        self.cropAxes = event.inaxes
        ndx = axes.index(event.inaxes)
        s = cam_list[ndx]
        self.croproi[ndx] = cam_config[s].crop
        roi_x = event.xdata
        roi_y = event.ydata
        x_center = self.croproi[ndx][1] / 2
        y_center = self.croproi[ndx][3] / 2
        logger.info(f"x: {roi_x}, y: {roi_y}")
        logger.info(f"dimensions: {self.frmDims}")
        logger.info(f"center x = {x_center}, center y = {y_center}")
        if roi_x < x_center:
            roi_x = x_center
        elif roi_x + x_center > self.frmDims[3]:
            roi_x = self.frmDims[3] - x_center
        roi_y = max(roi_y, y_center)
        if roi_y + y_center > self.frmDims[1]:
            roi_y = self.frmDims[1] - y_center
        self.croproi[ndx] = np.asarray(
            [
                roi_x - self.croproi[ndx][1] / 2,
                self.croproi[ndx][1],
                roi_y - self.croproi[ndx][3] / 2,
                self.croproi[ndx][3],
            ],
            int,
        )
        logger.info(self.croproi)
        # self.drawROI()

    def update_crop(self, index, axis, frmDims) -> None:
        self.frmDims = frmDims
        cpt = self.croproi[index]
        rec = [
            patches.Rectangle(
                (cpt[0], cpt[2]),
                cpt[1],
                cpt[3],
                fill=False,
                ec=[0.25, 0.25, 0.75],
                linewidth=2,
                linestyle="-",
                alpha=0.0,
            )
        ]
        self.croprec.append(axis.add_patch(rec[0]))

    def add_crop(self, crop: CropTupleType) -> None:
        self.croproi.append(crop)
