import wx

import numpy as np
from matplotlib.image import AxesImage

from rcp_task_acquisition.panels.ImagePanel import ImagePanel
from rcp_task_acquisition.panels.TrialPanel import TrialPanel
from rcp_task_acquisition.utils.camera_settings import CamSettings
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


class CalibrationPanel(TrialPanel):
    def __init__(self, parent: wx.Panel, *, psychopy_monitor: int = 0):
        super().__init__(parent)
        self.seconds = 0
        self.display_secs = 0
        self.display_mins = 0
        self.im: list[AxesImage] = []
        vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        vertical_sizer.Add(self._set_up_timer(), 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        self.SetSizer(vertical_sizer)
        self.rest_timer = wx.Timer(self)
        self.Bind(wx.EVT_TIMER, self.on_timer, self.rest_timer)
        # w = Window(screen=1, fullScreen=True)
        disp = None
        for idx in range(wx.Display.GetCount()):
            if idx == psychopy_monitor:
                disp = wx.Display(idx)
                break
        if disp is None:
            disp = wx.Display(0)
        logger.debug(
            "display: %s -> %s // %s", disp.GetName(), disp.GetGeometry(), disp.GetClientArea()
        )
        frame = self._frame_patient = wx.Frame(
            parent,
            title="Cameras",
            style=0,
            # style=wx.CLOSE_BOX
            # | wx.CLIP_CHILDREN
            # | wx.FRAME_FLOAT_ON_PARENT,
        )
        disp_size = disp.GetGeometry().GetSize()
        frame_size = wx.Size(int(disp_size.width * 0.8), int(disp_size.height * 0.5))
        # frame.SetSize(frame_size)
        disp_pos = disp.GetGeometry().GetPosition()
        frame.SetPosition(
            wx.Point(
                disp_pos.x + int((disp_size.width - frame_size.width) / 2),
                disp_pos.y + int(frame_size.height * 0.5),
            )
        )
        box_sizer = wx.BoxSizer(wx.VERTICAL)
        panel = self._patient_panel = wx.Panel(frame)
        # panel.SetSize(frame_size)
        box_sizer.Add(panel)
        frame.SetSizer(box_sizer)
        img_panel = self._image_panel = ImagePanel(panel)
        img_panel.SetSize(frame_size)
        img_panel.updateImage()
        panel.Fit()
        frame.Fit()
        frame.Show()
        logger.debug("frame: pos=%s ; size=%s", frame.GetPosition(), frame.GetSize())
        self.Bind(wx.EVT_WINDOW_DESTROY, self._on_destroyed, self)

    def _close_patient_win(self):
        logger.debug("_close_patient_win", stacklevel=3)
        self._frame_patient.Hide()
        self._frame_patient.Close()
        self._frame_patient = None

    def _on_destroyed(self, evt: wx.Event):
        self._close_patient_win()

    def Show(self, show: bool = True):
        logger.debug("showing with show=%s", show)
        self._frame_patient.Show(show)
        ret = super().Show(show)
        self.Update()
        return ret

    def Hide(self):
        logger.debug("Hide()")
        self._frame_patient.Hide()
        return super().Hide()

    def Close(self, force: bool = False) -> bool:
        self._close_patient_win()
        return super().Close(force)

    def prepare_cams(self, cams: list[CamSettings]):
        # logger.debug("received prepare cams: %s", cams)
        self._frame_patient.Show()
        imp = self._image_panel
        imp.updateImage()
        cam: CamSettings
        for idx, (axe, cam) in enumerate(zip(imp.axes, cams)):
            ims = axe.imshow(cam.frame)
            ims.set_clim(0, 255)
            self.im.append(ims)
            # self.cam_crop.update_crop(idx, axe, cam.frame_dims)
        cam0 = cams[0]
        cam1 = cams[1]
        imp.update_names([cam0.name, cam1.name])
        imp.draw()

    def _set_up_timer(self):
        self.seconds_text = wx.StaticText(self, label="Time: 0 mins, 0 secs")
        grid_sizer = wx.GridBagSizer(5, 4)
        grid_sizer.Add(
            self.seconds_text, pos=(4, 0), span=(0, 4), flag=wx.ALIGN_LEFT | wx.ALL, border=10
        )
        return grid_sizer

    def reset(self, count: int):
        self.seconds = 0
        self.seconds_text.SetLabel("Time: 0 mins, 0 secs")

    def on_timer(self, event):
        self.seconds += 1
        self.display_mins = int(self.seconds / 60)
        self.display_secs = self.seconds % 60
        self.seconds_text.SetLabel(f"Time: {self.display_mins} mins, {self.display_secs} secs")

    def on_camera_frame_update(self, index: int, frame: np.ndarray):
        self.im[index].set_data(frame)
        self._image_panel.figure.canvas.draw()

    def update_cams_viewed(self, cams: list[CamSettings]):
        for im, cam in zip(self.im, cams):
            im.set_data(cam.frame)
        self._image_panel.update_names(list(cam.name for cam in cams))
