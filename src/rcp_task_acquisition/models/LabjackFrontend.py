"""
A class to store the labjack events and functions that are controlled from the
frontend.
"""

import ctypes
import time
import typing
from multiprocessing import Array, Queue, Value
from typing import Any

import numpy as np
import wx

from rcp_task_acquisition.models.SerialDevice import SerialDevice
from rcp_task_acquisition.models.LabjackProcess import LabJackDataStream
from rcp_task_acquisition.panels.GraphPanel import GraphPanel
from rcp_task_acquisition.utils.constants import PLOT_CONSTANTS
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.typing import SharedBool, SharedInt, HardwareListsType, SharedArray

logger = get_logger(__name__)


class LabjackFrontend:
    def __init__(
        self,
        array_length: int,
        ctrl_panel: GraphPanel,
        timer: wx.Timer,
        button_pressed: SharedBool,
        press_count: SharedInt,
        hardware_test: SharedBool,
    ):
        self._serial_dev: SerialDevice | None = None
        self.constants: list[str] = []
        self.constant_index: list[int] = []
        self.button_pressed = button_pressed  # Value(ctypes.c_bool, False)
        self.labjack_list: list[str] = []
        #     item for item in list(args[1]) if item not in self.constants
        # ]  # list(args[1])
        self.hardware: list[str] = []
        #     item for item in list(args[0]) if item not in PLOT_CONSTANTS
        # ]  # list(args[0])
        self.voltage_ranges: tuple[tuple[float, float], ...] = ()
        self.hardware_indices = (
            Value(ctypes.c_int, -1),
            Value(ctypes.c_int, -1),
            Value(ctypes.c_int, -1),
        )
        self.prev_graph_list = [-1, -1, -1]
        self.digital_list: list[int] = []
        self.analog_list: list[str] = []
        self.button_list: list[int | tuple[int, str]] = []
        self.extended_list: list[int] = []
        self.array_length: int = array_length
        for index, item in enumerate(self.labjack_list):
            if "F" in item:
                self.digital_list.append(int(item[-1]))
                logger.debug(f"hardware: {self.hardware[index]}")
                if "Accessory" in self.hardware[index]:
                    self.button_list.append(int(item[-1]))
            else:
                self.analog_list.append(item)
        self.inputs_list: tuple[list[str], list[int], list[int]] = (
            self.analog_list,
            self.digital_list,
            self.extended_list,
        )
        self.labjack_arr: SharedArray[int] = Array(
            "d", array_length * (len(self.hardware_indices) + 3)
        )
        self.labjack_queue: Queue[Any] = Queue()
        self.labjack_is_csv = Value(ctypes.c_bool, False)
        self.stream_started = Value(ctypes.c_bool, False)
        self.labjack_is_finished = Value(ctypes.c_bool, True)
        self.scan_rate = Value(ctypes.c_float, 0)
        self.hardware_test = hardware_test
        self.graph_panel = ctrl_panel
        self.labjack_choices = self.graph_panel.get_graph_choices()
        self.labjack_timer = timer
        self.press_count = press_count
        logger.debug(f"button {self.button_list}")
        self.graph_panel.set_constants(self.constants)
        for choice in self.labjack_choices:
            choice.Bind(wx.EVT_CHOICE, self._update_graph_list)
        self.handshake = Value(ctypes.c_int, False)
        self.serial_state = 0
        self.labjack_process: LabJackDataStream
        self.msg = ""

    def labjack_stream(self, even: wx.Event) -> None:
        labjack_button = self.graph_panel.get_graph_button()
        if labjack_button.GetValue():
            labjack_button.SetLabel("Stop Labjack")
            self.stop_labjack()
            self.start_labjack()
        else:
            self.stop_labjack()
            labjack_button.SetLabel("Stream Labjack")
            labjack_button.SetValue(False)

    def update_hardware(
        self,
        hardware_lists: HardwareListsType,
    ) -> None:
        self.graph_panel.update_graph(hardware_lists)
        self.hardware = list(hardware_lists[0])
        self.labjack_list = list(hardware_lists[1])
        self.constant_index = []
        self.constants = []
        for index, constant in enumerate(PLOT_CONSTANTS):
            hardware_index = self.hardware.index(constant)
            self.constants.append(self.labjack_list[hardware_index])
            self.constant_index.append(hardware_index)

        self.voltage_ranges = hardware_lists[3]
        self.digital_list = []
        self.analog_list = []
        self.button_list = []
        self.extended_list = []  # nothing append to it, but it's fed in an output list,
        # which is "consumed" downstream.
        for index, item in enumerate(self.labjack_list):
            logger.info(f"self.all_hardware: {item}")
            if "F" in item:
                self.digital_list.append(int(item[-1]))
                logger.debug(f"hardware: {self.labjack_list[index]}")
                if "Accessory" in self.hardware[index]:
                    self.button_list.append((int(item[-1]), "f"))
            elif "E" in item:
                self.digital_list.append(int(item[-1]) + 8)
                if "Accessory" in self.hardware[index]:
                    self.button_list.append((int(item[-1]) + 8, "e"))
            # elif "E" in item:
            #     self.extended_list.append(int(item[-1]))
            #     if "Button" in self.all_hardware[0][index]:
            #         self.button_list.append((int(item[-1]), "e"))
            else:
                self.analog_list.append(item)
        logger.info(
            f"digital: {self.digital_list}, extended: {self.extended_list}, Analog: {self.analog_list}, button: {self.button_list}"
        )
        self.inputs_list = (self.analog_list, self.digital_list, self.extended_list)
        logger.debug(self.button_list)
        self._update_graph_list("")

    def start_labjack(self) -> bool:
        if not self.labjack_is_finished.value:
            logger.info("labjack is currently runninng")
            return True
        logger.debug(self.hardware)
        logger.debug(self.hardware_indices)
        self.scan_rate.value = 0
        self.labjack_is_finished.value = False
        self.labjack_process = LabJackDataStream(
            self.array_length,
            self.labjack_is_finished,
            self.labjack_arr,
            self.labjack_is_csv,
            self.labjack_queue,
            self.labjack_list,
            self.hardware_indices,
            self.button_pressed,
            self.inputs_list,
            self.button_list,
            self.press_count,
            self.constant_index,
            self.voltage_ranges,
            self.stream_started,
            self.scan_rate,
            self.handshake,
        )

        if self.labjack_process.is_successful():
            self.labjack_process.start()
            self.labjack_timer.Start(200)
            return True
        else:
            # Warning("labjack").display()
            labjack_button = self.graph_panel.get_graph_button()
            labjack_button.SetValue(False)
            return False

    def stop_labjack(self) -> float:

        self.labjack_is_finished.value = True
        self.labjack_is_csv.value = False
        self.stream_started.value = False
        self.labjack_timer.Stop()
        for index, lj_input in enumerate(self.hardware_indices):
            self.graph_panel.update_yaxis([np.nan] * self.array_length, index, lj_input.value)
        for index, constant_inputs in enumerate(self.constants):
            self.graph_panel.update_constants(
                [np.nan] * self.array_length, index, self.constant_index[index]
            )
        new_arr = np.empty(80000 * (len(self.hardware_indices) + 3))

        new_arr.fill(np.nan)

        labjack_arr = self.labjack_arr.get_obj()
        np.frombuffer(labjack_arr, dtype=ctypes.c_double).reshape(  # type: ignore
            # eventual todo: cannot get type hint right yet with shared array and np.frombuffer(...)
            len(new_arr.flatten())
        )[:] = new_arr.flatten()
        self.graph_panel.draw()
        try:
            self.labjack_process.join()
        except Exception as err:
            logger.info("No open Labjack process: %s", err)
        logger.info("labjack_stopped")
        return self.scan_rate.value

    def labjack_event(self, event: wx.Event) -> None:
        if not self.labjack_is_finished.value and self.stream_started.value:
            arr_step = 0
            # if self.handshake.value == 1:
            y_plot_points = np.frombuffer(self.labjack_arr.get_obj(), "d", len(self.labjack_arr))  # type: ignore
            # else:
            #     return
            ser_dev = self._serial_dev
            if not np.isnan(y_plot_points[-1]) and ser_dev is not None:
                self.serial_state += 1
                if self.serial_state > 0:
                    self._serial_dev = None
                    ser_dev.write(self.msg)
                    time.sleep(2)
                    ser_dev.write("A")

            if not self.hardware_test.value:
                for index, lj_input in enumerate(self.hardware_indices):
                    if lj_input.value == -1:
                        self.graph_panel.update_yaxis(
                            [np.nan] * self.array_length, index, lj_input.value
                        )
                        y_plot_points[arr_step : arr_step + self.array_length] = np.nan
                        # arr_step+= self.array_length
                        self.graph_panel.set_visible(index, False)
                    else:
                        if lj_input.value != self.prev_graph_list[index]:
                            self.prev_graph_list[index] = lj_input.value
                            y_plot_points[arr_step : arr_step + self.array_length] = np.nan
                            self.graph_panel.update_yaxis(
                                [np.nan] * self.array_length, index, lj_input.value
                            )
                        self.graph_panel.update_yaxis(
                            y_plot_points[arr_step : arr_step + self.array_length],
                            index,
                            lj_input.value,
                        )
                        self.graph_panel.set_visible(index)
                    arr_step += self.array_length
            else:
                for index, lj_input in enumerate(self.hardware_indices):
                    self.graph_panel.set_visible(index, False)
                    arr_step += self.array_length

            for index, constants_input in enumerate(self.constants):
                self.graph_panel.update_constants(
                    y_plot_points[arr_step : arr_step + self.array_length],
                    index,
                    self.constant_index[index],
                )
                self.graph_panel.set_visible_const(index)
                arr_step += self.array_length
            # if self.handshake.value == 1:
            np.frombuffer(self.labjack_arr.get_obj(), dtype=ctypes.c_double).reshape(  # type: ignore
                len(y_plot_points.flatten())
            )[:] = y_plot_points.flatten()
            # self.handshake.value = 0
            self.graph_panel.draw()

    def add_csv(self, labjack_file: str, serial: SerialDevice, msg: str) -> None:
        self.labjack_csv = labjack_file
        self.labjack_queue.put(labjack_file)
        self.labjack_is_csv.value = True

        self.serial_state = 0
        self._serial_dev = serial
        self.msg = msg

    def is_active(self) -> bool:
        return not self.labjack_is_finished.value

    def _update_graph_list(self, event: wx.Event) -> None:
        selected_list = []

        for choice in self.labjack_choices:
            selection = choice.GetSelection()
            if selection not in (0, 1):
                choices = choice.GetStrings()
                selection = choices[selection]
                original_selection = self.hardware.index(selection)
                selected_list.append(original_selection)
        for index, choice in enumerate(self.labjack_choices):
            try:
                choice_sel = choice.GetSelection()
                selection = choice_sel if choice_sel != 0 else -1
                if selection != -1:
                    choices = choice.GetStrings()
                    selection = choices[selection]
                    original_selection = self.hardware.index(selection)
                else:
                    original_selection = -1
                new_options = [
                    hardware
                    for index, hardware in enumerate(self.hardware)
                    if index not in selected_list or index == original_selection
                ]
                new_options.insert(0, " ")
                choice.SetItems(new_options)

                if selection != -1:
                    assert isinstance(selection, str)
                    choice.SetSelection(new_options.index(selection))
                self.hardware_indices[index].value = original_selection
                self.graph_panel.update_label(index, selection)
            except Exception as err:
                logger.error("_update_graph_list: %s", err, stacklevel=2)
