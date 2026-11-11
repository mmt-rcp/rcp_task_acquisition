import matplotlib.axes
import numpy as np
import wx
from matplotlib import patches

from rcp_task_acquisition.utils import config
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.typing import CropTupleT, FrameDimsTupleT

logger = get_logger(__name__)


class Crop:
    def __init__(self) -> None:
        self.croprec: list[matplotlib.patches.Rectangle] = []
        self.croproi: list[CropTupleT] = []
        self.set_crop = None
        self.frmDims: FrameDimsTupleT = (0, 0, 0, 0)

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
        rec = self.croprec[ndx]
        roi = self.croproi[ndx]
        rec.set_x(roi[0])
        rec.set_y(roi[2])
        rec.set_width(roi[1])
        rec.set_height(roi[3])
        # if not self.croproi[ndx][0] == 0:
        #     self.croprec[ndx].set_alpha(0.6)
        # self.figure.canvas.draw()

    def adjust_crop(self, event, axes, cam_list, cam_config: config.CamerasDictConfig) -> None:
        self.cropAxes = event.inaxes
        ndx = axes.index(event.inaxes)
        s = cam_list[ndx]
        croproi = self.croproi[ndx] = cam_config[s].crop
        roi_x = event.xdata
        roi_y = event.ydata
        x_center = croproi[1] / 2
        y_center = croproi[3] / 2
        logger.info("x: %s, y: %s", roi_x, roi_y)
        logger.info("dimensions: %s", self.frmDims)
        logger.info("center x = %s, center y = %s", x_center, y_center)
        if roi_x < x_center:
            roi_x = x_center
        elif roi_x + x_center > self.frmDims[3]:
            roi_x = self.frmDims[3] - x_center
        roi_y = max(roi_y, y_center)
        if roi_y + y_center > self.frmDims[1]:
            roi_y = self.frmDims[1] - y_center
        self.croproi[ndx] = np.asarray(
            [
                roi_x - croproi[1] / 2,
                croproi[1],
                roi_y - croproi[3] / 2,
                croproi[3],
            ],
            int,
        )
        logger.info("croproi: %s", self.croproi)
        # self.drawROI()

    def update_crop(self, index: int, axis: matplotlib.axes.Axes, frmDims: FrameDimsTupleT) -> None:
        self.frmDims = frmDims
        cpt = self.croproi[index]
        rec = patches.Rectangle(
            (cpt[0], cpt[2]),
            cpt[1],
            cpt[3],
            fill=False,
            ec=[0.25, 0.25, 0.75],
            linewidth=2,
            linestyle="-",
            alpha=0.0,
        )
        rec_patched = axis.add_patch(rec)
        self.croprec.append(rec_patched)  # type: ignore

    def add_crop(self, crop: CropTupleT) -> None:
        self.croproi.append(crop)
