import wx
import wx.lib.dialogs
import numpy as np
import matplotlib as mpl
import matplotlib.backend_bases
from matplotlib.image import AxesImage

from rcp_task_acquisition.panels.ImagePanel import ImagePanel
from rcp_task_acquisition.utils.camera_settings import CamSettings
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


class CamerasView:
    def __init__(self, *, patient_monitor: int = 0):
        super().__init__()
        # for camera views on patient screen:
        self.im: list[AxesImage] = []
        disp = None
        for idx in range(wx.Display.GetCount()):
            if idx == patient_monitor:
                disp = wx.Display(idx)
                break
        if disp is None:
            disp = wx.Display(0)
        logger.debug(
            "display: %s -> %s // %s", disp.GetName(), disp.GetGeometry(), disp.GetClientArea()
        )
        frame = self._frame_patient = wx.Frame(
            None,
            title="Cameras",
            style=0,
            # style=wx.CLOSE_BOX
            # | wx.CLIP_CHILDREN
            # | wx.FRAME_FLOAT_ON_PARENT,
        )
        disp_size = disp.GetGeometry().GetSize()
        frame_size = wx.Size(int(disp_size.width * 0.8), int(disp_size.height * 0.5))
        disp_pos = disp.GetGeometry().GetPosition()
        frame.SetPosition(
            wx.Point(
                disp_pos.x + int((disp_size.width - frame_size.width) / 2),
                disp_pos.y + int(frame_size.height * 0.5),
            )
        )
        #
        img_panel = self._image_panel = ImagePanel(frame)
        img_panel.SetSize(frame_size)
        img_panel.updateImage()
        frame.Fit()
        frame.Hide()
        logger.debug("frame: pos=%s ; size=%s", frame.GetPosition(), frame.GetSize())

    @property
    def frame(self) -> wx.Frame:
        return self._frame_patient

    @property
    def image_panel(self) -> ImagePanel:
        return self._image_panel

    def on_camera_frame_update(self, index: int, frame: np.ndarray):
        """Allow a panel to intercept camera frame read from shared array, for display purpose"""
        self.im[index].set_data(frame)
        self._image_panel.draw()
        # logger.debug("cam%s updated", index)

    def update_cams_viewed(self, cams: list[CamSettings]):
        cam_names = list(cam.name for cam in cams)
        logger.debug("updating cams: %s", cam_names)
        self.prepare_cams(cams)
        for im, cam in zip(self.im, cams):
            im.set_data(cam.frame)

    def prepare_cams(self, cams: list[CamSettings]):
        logger.debug("received prepare cams: %s", [cam.name for cam in cams])
        imp = self._image_panel
        self.im.clear()
        cam: CamSettings
        for idx, (axe, cam) in enumerate(zip(imp.axes, cams)):
            ims = axe.imshow(cam.frame)
            ims.set_clim(0, 255)
            self.im.append(ims)
            # self.cam_crop.update_crop(idx, axe, cam.frame_dims)
        if len(cams) >= 2:
            cam0 = cams[0]
            cam1 = cams[1]
            imp.update_names([cam0.name, cam1.name])
        imp.draw()
