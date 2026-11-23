import mss
import numpy
import numpy as np
import wx
import wx.lib.dialogs

from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


def get_proportions(original_size, scaled_width):
    # basing proportions on width bc there is less wiggle room on the display
    scale_factor = scaled_width / original_size[0]
    scaled_height = int(original_size[1] * scale_factor)
    return (scaled_width, scaled_height)


class MonitorPanel(wx.Panel):
    monitor_bitmap: wx.StaticBitmap

    def __init__(self, parent: wx.Panel, psychopy_monitor: int, display_size: wx.Size):
        super().__init__(parent, style=wx.NO_FULL_REPAINT_ON_RESIZE)
        self.parent = parent
        self.psychopy_monitor = psychopy_monitor
        max_gui_image_size = (346, 216)
        self.display_size = get_proportions(display_size, max_gui_image_size[0])
        self.prev_arr: np.ndarray | None = None

        title = wx.StaticText(self, label="Participant Monitor:")
        font = wx.Font(wx.FontInfo(8).Bold())
        title.SetFont(font)

        self.monitor_bitmap = wx.StaticBitmap(self, wx.ID_ANY)
        self.monitor_bitmap.SetBitmap(wx.NullBitmap)

        image_sizer = wx.GridBagSizer(3, 4)
        image_sizer.Add(
            title, pos=(0, 0), span=(0, 4), flag=wx.ALIGN_CENTER_HORIZONTAL | wx.LEFT, border=0
        )
        image_sizer.Add(
            self.monitor_bitmap, pos=(1, 0), span=(0, 4), flag=wx.ALIGN_LEFT | wx.LEFT, border=0
        )
        self.SetSizer(image_sizer)

        self.Bind(wx.EVT_PAINT, self.on_paint)
        self.Bind(wx.EVT_SIZE, self.on_size)

        self.image: numpy.ndarray | None = None
        self.prev_image: numpy.ndarray | None = None
        self.update_screen()
        self.on_paint()
        self.Layout()

    def update_screen(self) -> None:
        # logger.debug("update_screen()")
        with mss.MSS() as sct:
            monitor = sct.monitors[self.psychopy_monitor + 1]
            # logger.debug("update_screen: sct=%s monitors=%s", sct, monitor)
            shot = sct.grab(monitor)
            prev = self.prev_image
            img = np.array(shot)
        # only update the gui when they are different
        if prev is not None and np.array_equal(img, prev):
            return
        self.image = img
        self.Refresh()

    def on_paint(self, event: wx.Event | None = None) -> None:
        img = self.image
        if img is None:
            return  # No image
        self.image = None
        self.prev_image = img
        rgb = img[:, :, :3][:, :, ::-1]
        h, w = rgb.shape[:2]
        wx_image = wx.Image(w, h)
        wx_image.SetData(rgb.tobytes())
        wx_image = wx_image.Scale(self.display_size[0], self.display_size[1])
        bitmap = wx_image.ConvertToBitmap()
        # logger.debug("on_paint: shape=%s", rgb.shape)
        self.monitor_bitmap.SetBitmap(bitmap)
        self.monitor_bitmap.Refresh()

    def on_size(self, event: wx.Event) -> None:
        self.Refresh()
        event.Skip()
