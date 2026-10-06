from dataclasses import dataclass
from multiprocessing import Queue

import PySpin
import wx

from rcp_task_acquisition.models.Warnings import WarnCat, WarningHandler
from rcp_task_acquisition.utils import config
from rcp_task_acquisition.utils.config import HardwareItem, RcpTasksGroupConfig
from rcp_task_acquisition.utils.constants import (
    ANALOG_RANGES,
    CAMERA_HEADERS,
    HEADERS,
    LABJACK_PIN_LIST,
)
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.multiprocess import ProcessWithLogging
from rcp_task_acquisition.utils.run_context import RcpRunContext

logger = get_logger(__name__)


# keeping track of each row for the hardware/camera selection
# keeping cameras and hardware seperate since we handle them differently in setup and values needed
@dataclass
class HardwareRow:
    name: wx.StaticText
    in_use: wx.CheckBox
    labjack: wx.Choice
    voltage_range: wx.Choice
    in_use_all: bool = False
    in_use_protocol: bool = False


@dataclass
class CameraRow:
    name: wx.StaticText
    in_use: wx.CheckBox
    is_primary: wx.RadioButton
    serial: wx.Choice
    framerate_decrease: wx.Choice
    # gig_e: wx.Choice #wx.CheckBox
    flip_vid: wx.CheckBox
    in_use_all: bool = False
    in_use_protocol: bool = False


class CamProcess(ProcessWithLogging):
    """
    For some reason the PySpin instance does not like being created on the main thread.
    (it works here and then will cause freezing when trying to run the main gui)
    So our current fix is to put it on its own process

    Attributes:
        cam_serial_numbers (list): a list of the cameras that pyspin can currently
                                   access.
    """

    def __init__(self, cam_queue):
        super().__init__()
        self.cam_queue = cam_queue

    def run(self):
        system = PySpin.System.GetInstance()
        cam_list = system.GetCameras()
        count = 0
        for camera in cam_list:
            nodemap_tldevice = camera.GetTLDeviceNodeMap()
            node_device_serial_number = PySpin.CStringPtr(
                nodemap_tldevice.GetNode("DeviceSerialNumber")
            )
            if PySpin.IsReadable(node_device_serial_number):
                logger.debug(node_device_serial_number.GetValue())
                self.cam_queue.put(node_device_serial_number.GetValue())
                count += 1
            camera.DeInit()
            del camera
        self.cam_queue.put("done")
        cam_list.Clear()

        system.ReleaseInstance()


class HardwarePanel(wx.Panel):
    """
    The initial panel where the user can select the hardware and task to run

    """

    def __init__(
        self, tasks_config: RcpTasksGroupConfig, parent=None, *, rcp_context: RcpRunContext
    ):
        self._rcp_context: RcpRunContext = rcp_context
        self.args = None
        self.row_list = [member.value for member in HardwareItem]
        self.hardware_list: list[HardwareRow] = []
        self.camera_list: list[CameraRow] = []
        self.cam_serial_numbers: list[str] = []
        self.labjack_selection = LABJACK_PIN_LIST
        self.select_protocol = False
        self.tasks_config = tasks_config
        self.task = None
        self.border = 10
        self.task_list = list(self.tasks_config.keys())

        user_input_count = 1
        while len(self.row_list) < len(LABJACK_PIN_LIST) + 1:
            self.row_list.append(f"userInput{user_input_count}")
            user_input_count += 1

        super().__init__(parent)
        vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        vertical_sizer.Add(self._setup_protocol(), 0, wx.EXPAND | wx.ALL, 10)
        vertical_sizer.Add(self._setup_camera_panel(), 0, wx.EXPAND | wx.ALL, 10)
        vertical_sizer.Add(self._setup_labjack(), 0, wx.EXPAND | wx.ALL, 10)
        self.SetSizerAndFit(vertical_sizer)

    def _setup_protocol(self):
        self.save_button = wx.Button(self, label="Save Hardware Settings")
        self.save_button.Bind(wx.EVT_BUTTON, self.save_event)

        self.hardware_radio = wx.RadioButton(self, label="Update All Hardware", style=wx.RB_GROUP)
        self.hardware_radio.Bind(wx.EVT_RADIOBUTTON, self.hardware_radio_pressed)

        self.protocol_radio = wx.RadioButton(self, label="Update Current Protocol")
        self.protocol_radio.Bind(wx.EVT_RADIOBUTTON, self.task_radio_pressed)

        grid_sizer = wx.GridBagSizer(6, 1)

        grid_sizer.Add(
            self.hardware_radio,
            pos=(0, 0),
            span=(0, 2),
            flag=wx.ALIGN_CENTER | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            self.protocol_radio,
            pos=(0, 2),
            span=(0, 2),
            flag=wx.ALIGN_CENTER | wx.ALL,
            border=self.border,
        )
        grid_sizer.Add(
            self.save_button,
            pos=(0, 4),
            span=(0, 2),
            flag=wx.ALIGN_CENTER | wx.ALL,
            border=self.border,
        )
        return grid_sizer

    def _setup_labjack(self):
        ctx = self._rcp_context
        user_input_list = []
        user_input_count = 0
        vertical_pos = 0
        horizontal_pos = 0

        labjack_sizer = wx.GridBagSizer(len(HEADERS), len(HardwareItem))
        for header in HEADERS:
            new_header = wx.StaticText(self, label=header)
            labjack_sizer.Add(
                new_header,
                pos=(vertical_pos, horizontal_pos),
                span=(0, 1),
                flag=wx.ALL,
                border=self.border,
            )
            horizontal_pos += 1
        vertical_pos += 1

        # to get any user added hardware names
        for hardware, hard_cfg in ctx.user_config.hardware.items():
            if hardware not in self.row_list:
                user_input_list.append(hardware)
        for hardware in self.row_list:
            in_use = wx.CheckBox(self, id=wx.ID_ANY)
            in_use.Bind(wx.EVT_CHECKBOX, self.update_options)

            name = (
                wx.StaticText(self, label=hardware)
                if "user" not in hardware.lower()
                else wx.TextCtrl(self, value=hardware)
            )
            name.Enable(False)

            labjack = wx.Choice(self, id=wx.ID_ANY, choices=LABJACK_PIN_LIST)
            labjack.Bind(wx.EVT_CHOICE, self._on_choice_labjack)
            labjack.Enable(False)

            analog_strings = [str(volt_range) for volt_range in ANALOG_RANGES]
            voltage_ranges = wx.Choice(self, id=wx.ID_ANY, choices=analog_strings)
            voltage_ranges.SetSelection(0)
            voltage_ranges.Enable(False)
            voltage_ranges.Hide()
            labjack_sizer.Add(
                in_use,
                pos=(vertical_pos, 0),
                span=(0, 1),
                flag=wx.ALIGN_CENTER | wx.ALL,
                border=self.border,
            )
            labjack_sizer.Add(
                name,
                pos=(vertical_pos, 1),
                span=(0, 1),
                flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL,
                border=self.border,
            )
            labjack_sizer.Add(
                labjack,
                pos=(vertical_pos, 2),
                span=(0, 1),
                flag=wx.ALIGN_CENTER | wx.ALL,
                border=self.border,
            )

            labjack_sizer.Add(
                voltage_ranges,
                pos=(vertical_pos, 3),
                span=(0, 1),
                flag=wx.ALIGN_CENTER | wx.ALL,
                border=self.border,
            )
            vertical_pos += 1
            logger.debug(f"hardware:  {hardware}")
            new_hardware = HardwareRow(
                name, in_use, labjack, voltage_ranges
            )  # min_graph, max_graph, voltage_ranges)
            if hardware in ctx.user_config.hardware:
                hard_cfg = ctx.user_config.hardware[hardware]
                labjack.Enable(True)
                name.Enable(True)
                in_use.SetValue(True)
                new_hardware.in_use_all = True
                labjack_value = LABJACK_PIN_LIST.index(hard_cfg.labjack_input)
                labjack.SetSelection(labjack_value)
                voltage_ranges.Enable(True)

                if "A" in hard_cfg.labjack_input:
                    volt_index = ANALOG_RANGES.index(hard_cfg.voltage_range[1])
                    voltage_ranges.SetSelection(volt_index)

            elif "user" in hardware.lower() and user_input_count < len(user_input_list):
                voltage_ranges.Enable(True)
                # if "voltage_range" in hardware_config[hardware]:
                if hardware in ctx.user_config.hardware:
                    hard_cfg = ctx.user_config.hardware[hardware]
                    # voltage_ranges.SetSelection(str(hard_cfg.voltage_range))  # TODO
                else:
                    hard_cfg = config.HardwareItemConfig()

                labjack.Enable(True)
                name.Enable(True)
                in_use.SetValue(True)
                new_hardware.in_use_all = True
                new_hardware.in_use_all = True
                cur_user = user_input_list[user_input_count]
                name.SetValue(cur_user)
                labjack_value = LABJACK_PIN_LIST.index(hard_cfg.labjack_input)
                labjack.SetSelection(labjack_value)
                user_input_count += 1

            self.hardware_list.append(new_hardware)
        self._update_lists(self.hardware_list)

        labjack_box = wx.StaticBox(self, label="Labjack Setup")
        hardware_sizer = wx.StaticBoxSizer(labjack_box, wx.HORIZONTAL)
        hardware_sizer.Add(labjack_sizer, 1, wx.EXPAND | wx.ALL, 15)
        return hardware_sizer

    def _get_serial_numbers(self):
        cam_queue = Queue()
        camera = CamProcess(cam_queue)
        camera.start()
        while True:
            serial_number = cam_queue.get()
            if serial_number == "done":
                break
            self.cam_serial_numbers.append(serial_number)
        camera.join()

    def _setup_camera_panel(self):
        first_cam = True
        self._get_serial_numbers()
        # cam_config = self.user_config["cameras"]
        grid_sizer = wx.GridBagSizer(len(CAMERA_HEADERS), len(self.cam_serial_numbers))
        vertical_pos = 0
        horizontal_pos = 0

        for header in CAMERA_HEADERS:
            new_header = wx.StaticText(self, label=header)
            grid_sizer.Add(
                new_header,
                pos=(vertical_pos, horizontal_pos),
                span=(0, 1),
                flag=wx.ALL,
                border=self.border,
            )
            horizontal_pos += 1
        vertical_pos += 1

        for key, cfg in self._rcp_context.user_config.cameras.items():
            in_use = wx.CheckBox(self, id=wx.ID_ANY)
            in_use.Bind(wx.EVT_CHECKBOX, self.update_options)

            name = wx.StaticText(self, label=key)
            name.Enable(False)

            serial = wx.Choice(self, choices=self.cam_serial_numbers)
            serial.Bind(wx.EVT_CHOICE, self._on_choice_cameras)
            serial.Enable(False)

            is_primary = (
                wx.RadioButton(self, style=wx.RB_GROUP) if first_cam else wx.RadioButton(self)
            )

            self.framerate_decrease_options = ["1", "2"]
            framerate_decrease = wx.Choice(
                self, id=wx.ID_ANY, choices=self.framerate_decrease_options
            )
            framerate_decrease.Enable(False)
            # gig_e = wx.CheckBox(self, id=wx.ID_ANY)
            # gig_e.Enable(False)

            flip_vid = wx.CheckBox(self, id=wx.ID_ANY)
            flip_vid.Enable(False)

            first_cam = False
            is_primary.Enable(False)

            new_camera = CameraRow(
                name, in_use, is_primary, serial, framerate_decrease, flip_vid
            )  # gig_e, flip_vid)

            grid_sizer.Add(
                in_use, pos=(vertical_pos, 0), span=(0, 1), flag=wx.ALIGN_CENTER | wx.ALL, border=10
            )
            grid_sizer.Add(
                name,
                pos=(vertical_pos, 1),
                span=(0, 1),
                flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL,
                border=10,
            )
            grid_sizer.Add(
                is_primary,
                pos=(vertical_pos, 2),
                span=(0, 1),
                flag=wx.ALIGN_CENTER | wx.ALL,
                border=10,
            )
            grid_sizer.Add(
                serial, pos=(vertical_pos, 3), span=(0, 1), flag=wx.ALIGN_CENTER | wx.ALL, border=10
            )
            # grid_sizer.Add(gig_e, pos=(vertical_pos, 4), span=(0,1), flag=wx.ALIGN_CENTER | wx.ALL, border=10)
            grid_sizer.Add(
                framerate_decrease,
                pos=(vertical_pos, 4),
                span=(0, 1),
                flag=wx.ALIGN_CENTER | wx.ALL,
                border=10,
            )
            grid_sizer.Add(
                flip_vid,
                pos=(vertical_pos, 5),
                span=(0, 1),
                flag=wx.ALIGN_CENTER | wx.ALL,
                border=10,
            )
            vertical_pos += 1

            if cfg.in_use and cfg.serial in self.cam_serial_numbers:
                new_camera.in_use_all = True
                in_use.SetValue(True)
                name.Enable(True)
                serial.Enable(True)
                is_primary.Enable(True)
                # gig_e.Enable(True)
                framerate_decrease.Enable(True)
                flip_vid.Enable(True)
                flip_vid.SetValue(cfg.flip)
                # gig_e.SetValue(cam_config[key]["gig_e"])
                # try:
                index = self.framerate_decrease_options.index(str(cfg.framerate_decrease_factor))
                framerate_decrease.SetSelection(index)
                # except:
                #     pass
                is_primary.SetValue(cfg.ismaster)
                cam_index = self.cam_serial_numbers.index(cfg.serial)
                serial.SetSelection(cam_index)

            self.camera_list.append(new_camera)
        self._update_lists(self.camera_list, is_labjack=False)

        camera_box = wx.StaticBox(self, label="Camera Setup")
        camera_sizer = wx.StaticBoxSizer(camera_box, wx.HORIZONTAL)
        camera_sizer.Add(grid_sizer, 1, wx.EXPAND | wx.ALL, 15)

        return camera_sizer

    def hardware_radio_pressed(self, event):
        # update to show active hardware
        self.select_protocol = False
        for hardware in self.hardware_list:
            if hardware.in_use_all:
                hardware.in_use.SetValue(True)
            hardware.in_use.Enable(True)
        for camera in self.camera_list:
            if camera.in_use_all:
                camera.in_use.SetValue(True)
            camera.in_use.Enable(True)
        self.update_options(event)

    def task_radio_pressed(self, event):
        # update to show available hardware for task
        self.select_protocol = True

        for hardware in self.hardware_list:
            if not hardware.in_use.GetValue():
                hardware.in_use.Enable(False)
                hardware.name.Enable(False)
            else:
                hardware.in_use_all = True
                hardware.name.Enable(True)
            hardware.in_use.SetValue(False)
            hardware.voltage_range.Enable(False)
            hardware.labjack.Enable(False)
        for camera in self.camera_list:
            if not camera.in_use.GetValue():
                camera.in_use.Enable(False)
                camera.name.Enable(False)
            else:
                camera.in_use_all = True
                camera.name.Enable(True)
            camera.in_use.SetValue(False)
            camera.serial.Enable(False)
            camera.is_primary.Enable(False)
            # camera.gig_e.Enable(False)
            camera.framerate_decrease.Enable(False)
            camera.flip_vid.Enable(False)

        self.update_task()
        self._update_lists(self.hardware_list)
        self._update_lists(self.camera_list, is_labjack=False)

    def update_options(self, event):
        for hardware in self.hardware_list:
            if self.hardware_radio.GetValue():
                if hardware.in_use.GetValue():
                    hardware.in_use_all = True
                else:
                    hardware.in_use_all = False
        for camera in self.camera_list:
            if self.hardware_radio.GetValue():
                if camera.in_use.GetValue():
                    camera.in_use_all = True
                else:
                    camera.in_use_all = False
        if not self.select_protocol:
            for hardware in self.hardware_list:
                if hardware.in_use.GetValue():
                    hardware.name.Enable(True)
                    hardware.labjack.Enable(True)
                    hardware.voltage_range.Enable(True)
                else:
                    hardware.name.Enable(False)
                    hardware.labjack.Enable(False)
                    hardware.voltage_range.Enable(False)
                    hardware.labjack.SetSelection(-1)
                    hardware.voltage_range.Hide()
            for camera in self.camera_list:
                if camera.in_use.GetValue():
                    camera.name.Enable(True)
                    camera.is_primary.Enable(True)
                    camera.serial.Enable(True)
                    # camera.gig_e.Enable(True)
                    # camera.gig_e.Enable(False)
                    camera.framerate_decrease.Enable(True)
                    camera.flip_vid.Enable(True)

                else:
                    camera.name.Enable(False)
                    camera.serial.Enable(False)
                    camera.is_primary.Enable(False)
                    # camera.gig_e.Enable(False)
                    camera.flip_vid.Enable(False)
                    camera.serial.SetSelection(-1)
            self._update_lists(self.hardware_list)
            self._update_lists(self.camera_list, is_labjack=False)

    def save_event(self, event):
        ctx = self._rcp_context
        cameras = self._update_cameras_config()
        if cameras is None:
            return
        ctx.user_config.cameras = cameras
        hardware_items_cfg = self._create_hardware_config()
        if hardware_items_cfg is None:
            WarningHandler(WarnCat.NO_HARDWARE).display()
            return
        ctx.user_config.hardware = hardware_items_cfg

        if self.select_protocol:
            self.args = []

            for hardware in self.hardware_list:
                if hardware.in_use.GetValue():
                    name = self._get_name(hardware)
                    self.args.append(name)
            for camera in self.camera_list:
                if camera.in_use.GetValue():
                    name = self._get_name(camera)
                    self.args.append(name)
            self.tasks_config[self.task].settings = self.args
            config.save_rcp_tasks_config(
                self.tasks_config, ctx.config_dir.joinpath("taskconfig.yaml")
            )
            # write_config("taskconfig.yaml", self.task_config)
        config.save_rcp_user_config(ctx.user_config, ctx.config_dir.joinpath("userdata.yaml"))
        # write_config("userdata.yaml", dataclasses.asdict(ctx.user_config))
        dlg = wx.MessageDialog(
            None, "Hardware settings saved!", "Notification", wx.OK | wx.ICON_INFORMATION
        )
        dlg.ShowModal()
        dlg.Destroy()

    def _create_hardware_config(self) -> config.HardwareDictConfig | None:
        cfg = config.HardwareDictConfig()
        for hardware in self.hardware_list:
            if hardware.in_use_all:
                labjack_pin = hardware.labjack.GetCurrentSelection()
                if labjack_pin == -1:
                    WarningHandler(WarnCat.HARDWARE).display()
                    return None
                name = self._get_name(hardware)
                if not name:
                    WarningHandler(WarnCat.NAME).display()
                    return None
                labjack_list = hardware.labjack.GetStrings()
                labjack_value = labjack_list[labjack_pin]
                voltage_range = (0, 1)
                if "A" in labjack_value:
                    voltage = float(
                        hardware.voltage_range.GetStrings()[
                            hardware.voltage_range.GetCurrentSelection()
                        ]
                    )
                    voltage_range = (voltage * -1, voltage)
                cfg[name] = config.HardwareItemConfig(
                    labjack_input=labjack_value,
                    voltage_range=voltage_range,
                )
        return cfg

    def _update_cameras_config(self) -> config.CamerasDictConfig | None:
        ctx = self._rcp_context
        cameras = ctx.user_config.cameras
        for camera in self.camera_list:
            cam_name = self._get_name(camera)
            if camera.in_use_all:
                serial = camera.serial.GetCurrentSelection()
                if serial == -1:
                    WarningHandler(WarnCat.SERIAL).display()
                    return None
                cam_cfg = cameras.get(cam_name)
                if cam_cfg is not None:
                    cam_cfg.ismaster = camera.is_primary.GetValue()
                    cam_cfg.serial = camera.serial.GetStrings()[serial]
                    cam_cfg.in_use = camera.in_use_all
                    # if camera.gig_e.GetValue():
                    #     camera_dict[self._get_name(camera)]["framerate"] = int(240/2)
                    # else:
                    #     camera_dict[self._get_name(camera)]["framerate"] = int(240)
                    frame_decrease = self.framerate_decrease_options[
                        camera.framerate_decrease.GetSelection()
                    ]
                    cam_cfg.framerate_decrease_factor = int(frame_decrease)
                    # camera_dict[self._get_name(camera)]["gig_e"] = camera.gig_e.GetValue()
                    cam_cfg.flip = camera.flip_vid.GetValue()

                else:
                    frame_decrease = self.framerate_decrease_options[
                        camera.framerate_decrease.GetSelection()
                    ]
                    cameras[cam_name] = config.CameraConfig(
                        ismaster=camera.is_primary.GetValue(),
                        serial=camera.serial.GetStrings()[serial],
                        in_use=camera.in_use_all,
                        framerate_decrease_factor=int(frame_decrease),
                        # "gig_e": camera.gig_e.GetValue(),
                        flip=camera.flip_vid.GetValue(),
                    )
            else:
                cam_cfg = cameras[cam_name]
                cam_cfg.in_use = False
                cam_cfg.ismaster = False
        return cameras

    def _get_name(self, hardware):
        return (
            hardware.name.GetLabel() if hardware.name.GetLabel() != "" else hardware.name.GetValue()
        )

    def _on_choice_labjack(self, event):
        self._update_lists(self.hardware_list)

    def _on_choice_cameras(self, event):
        self._update_lists(self.camera_list, is_labjack=False)

    def _update_lists(self, item_list: list[CameraRow] | list[HardwareRow], is_labjack=True):
        selected_list = []
        primary_list = LABJACK_PIN_LIST if is_labjack else self.cam_serial_numbers
        # self._rcp_context
        for hardware in item_list:
            choice_list = hardware.labjack if is_labjack else hardware.serial
            if type(choice_list) == wx.Choice and choice_list.GetSelection() != -1:
                selection = choice_list.GetSelection()
                choices = choice_list.GetStrings()
                selection = choices[selection]
                original_selection = primary_list.index(selection)
                selected_list.append(original_selection)
        for hardware in item_list:
            choice_list = hardware.labjack if is_labjack else hardware.serial
            try:
                selection = choice_list.GetSelection()
                if selection != -1:
                    choices = choice_list.GetStrings()
                    selection = choices[selection]
                    original_selection = primary_list.index(selection)
                else:
                    original_selection = -1
                new_options = [
                    hardware
                    for index, hardware in enumerate(primary_list)
                    if index not in selected_list or index == original_selection
                ]

                choice_list.SetItems(new_options)
                if selection != -1:
                    choice_list.SetSelection(new_options.index(selection))
                    if isinstance(hardware, HardwareRow):
                        if "A" in primary_list[original_selection]:
                            hardware.voltage_range.Show()
                        else:
                            hardware.voltage_range.Hide()
                    self.Layout()
            except Exception as err:
                logger.exception("Error update lists: %s", err)

    def update_task(self):
        if self.task == None:
            for hardware in self.hardware_list:
                hardware.in_use.Enable(False)
                hardware.name.Enable(False)
                hardware.voltage_range.Enable(False)
            for camera in self.camera_list:
                camera.in_use.Enable(False)
                camera.name.Enable(False)
        elif self.select_protocol:
            for hardware in self.hardware_list:
                name = self._get_name(hardware)
                if name in self.tasks_config[self.task].settings and hardware.in_use_all:
                    hardware.in_use.SetValue(True)
                    hardware.in_use.Enable(True)
                    hardware.name.Enable(True)
                    hardware.voltage_range.Enable(False)
                else:
                    hardware.in_use.SetValue(False)
            for camera in self.camera_list:
                name = self._get_name(camera)
                if name in self.tasks_config[self.task].settings and camera.in_use_all:
                    camera.in_use.SetValue(True)
                    camera.in_use.Enable(True)
                    camera.name.Enable(True)
                else:
                    camera.in_use.SetValue(False)

    def set_task(self, task: str):
        self.task = task
        # update to show available hardware for task
        if self.IsShown() and self.protocol_radio.GetValue():
            self.select_protocol = True

            for hardware in self.hardware_list:
                if not hardware.in_use_all:
                    hardware.in_use.Enable(False)
                    hardware.name.Enable(False)
                else:
                    hardware.in_use_all = True
                    hardware.name.Enable(True)
                    hardware.in_use.Enable(True)
                hardware.in_use.SetValue(False)
                hardware.labjack.Enable(False)
            for camera in self.camera_list:
                if not camera.in_use_all:
                    camera.in_use.Enable(False)
                    camera.name.Enable(False)
                else:
                    camera.in_use_all = True
                    camera.name.Enable(True)
                    camera.in_use.Enable(True)
                camera.in_use.SetValue(False)
                camera.serial.Enable(False)
                camera.is_primary.Enable(False)

            self.update_task()
            self._update_lists(self.hardware_list)
            self._update_lists(self.camera_list, is_labjack=False)

    def reset_hardware(self):
        if not self.hardware_radio.GetValue():
            self.hardware_radio.SetValue(True)
            self.select_protocol = False
            for hardware in self.hardware_list:
                if hardware.in_use_all:
                    hardware.in_use.SetValue(True)
                hardware.in_use.Enable(True)
            for camera in self.camera_list:
                if camera.in_use_all:
                    camera.in_use.SetValue(True)
                camera.in_use.Enable(True)
            self.update_options(None)

    def get_task(self):
        return self.task
