import ctypes
import io
import multiprocessing
import queue
import time
from multiprocessing import sharedctypes
from pathlib import Path
from typing import Optional, Any

import numpy as np
from labjack import ljm

from rcp_task_acquisition.utils.constants import SCANS_PER_READ
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.process import set_high_prio
from rcp_task_acquisition.utils.multiprocess import ProcessWithLogging, ProcessWithCommands
from rcp_task_acquisition.utils.typing import SharedBool, SharedInt, SharedFloat, SharedEvent

logger = get_logger(__name__)


class LabJackDataStream(ProcessWithCommands):
    def __init__(
        self,
        arr_length: int,
        labjack_arr: sharedctypes.SynchronizedArray,
        labjack_list: list[str],
        graph_indices: tuple[SharedInt, SharedInt, SharedInt],
        button_pressed: SharedBool,
        inputs: tuple[list[str], list[int], list[int]],
        button_list: list[tuple[int, str]],
        press_counter: SharedInt,
        constants: list[int],
        voltage_ranges: tuple[tuple[float, float], ...],
        stream_started: SharedEvent,
        scan_rate: SharedFloat,
        handshake: SharedInt,
    ) -> None:
        self.voltage_range: dict[str, tuple[float, float]] = {}
        for index, val in enumerate(labjack_list):
            if "A" in val:
                self.voltage_range[val] = voltage_ranges[index]
        logger.debug(self.voltage_range)
        super().__init__()
        self.arr_length = arr_length
        self.attemptedscanRate = 40000
        self.button_pressed = button_pressed
        self.press_counter = press_counter
        self.analog_inputs: list[str] = inputs[0]
        self.digital_inputs: list[int] = inputs[1]
        self.extended_inputs: list[int] = inputs[2]
        self.stream_started = stream_started
        self.actualscanRate = scan_rate
        self.handshake = handshake
        for item in self.extended_inputs:
            self.digital_inputs.append(item + 8)
        logger.debug(
            "analog: %s, digital: %s, extended: %s",
            self.analog_inputs,
            self.digital_inputs,
            self.extended_inputs,
        )

        self.scan_list = self.analog_inputs
        self.scan_num = len(self.scan_list)
        if self.digital_inputs:
            self.scan_num += 1
        logger.debug("extended_inputs: %s", self.extended_inputs)
        logger.debug("digital_inputs: %s", self.digital_inputs)
        self.graph_arr = labjack_arr
        self.numpy_arr = np.empty((6, self.attemptedscanRate * 2))
        self.numpy_arr.fill(np.nan)
        self.results = np.empty(self.scan_num * SCANS_PER_READ)
        self.results.fill(np.nan)
        self.graph_indices = graph_indices
        self.prev_graphs = [index.value for index in self.graph_indices]
        self.button_list = button_list
        self.constants = constants
        self.extended = False
        aScanList = ljm.namesToAddresses(len(self.scan_list), self.scan_list)[0]
        if self.digital_inputs or self.extended_inputs:
            aScanList.append(2580)

        input_names: list[str] = []
        work_voltage_ranges: list[float] = []
        for key, volt_range in self.voltage_range.items():
            input_names.append(f"{key}_RANGE")
            work_voltage_ranges.append(volt_range[1])

        input_names.append("STREAM_CLOCK_SOURCE")
        work_voltage_ranges.append(0)
        self.input_names = input_names
        self.voltage_ranges = work_voltage_ranges
        logger.verbose("voltages_ranges: %s", self.voltage_ranges)
        self.handle: Optional[int] = None  # ljm handle ; it's a fd basically
        self._labjack_csv_fh: io.BufferedWriter | None = None

    def _disconnect(self):
        handle = self.handle
        if handle is None:
            return
        self.handle = None
        try:
            ljm.eStreamStop(handle)
        except ljm.ljm.LJMError as err:
            logger.warning("eStreamStop failed: %s ; but continuing..", err)
        finally:
            ljm.close(handle)

    def _attempt_connect(self, scan_list):
        self._disconnect()
        try:
            self.__attempt_connect(scan_list)
            return
        except ljm.ljm.LJMError as err:
            logger.warning("LJM: failed attempt connect: %s..", err, exc_info=True, stacklevel=2)
            # if err.errorCode == 2605:  # STREAM_IS_ACTIVE
            #     ljm.eStreamStop(self.handle)
        self._disconnect()
        ljm.closeAll()
        time.sleep(3)
        self.__attempt_connect(scan_list)

    def __attempt_connect(self, scan_list):
        numAddresses = len(scan_list)
        self.handle = ljm.openS("ANY", "ANY", "ANY")
        try:
            ljm.eStreamStop(self.handle)
        except ljm.ljm.LJMError as err:
            logger.verbose("eStreamStop before connect: %s ; but continuing", err)
        # ljm.writeLibraryConfigS("LJM_STREAM_TCP_RECEIVE_BUFFER_SIZE", 4194304)
        # ljm.writeLibraryConfigS("LJM_STREAM_TCP_RECEIVE_BUFFER_SIZE", 0)
        ljm_buff_sz = ljm.readLibraryConfigS("LJM_STREAM_TCP_RECEIVE_BUFFER_SIZE")
        logger.verbose("LJM_STREAM_TCP_RECEIVE_BUFFER_SIZE=%s", ljm_buff_sz)
        # see: https://share.google/aimode/dbpqwwqov0aM2cwJs
        # Key Details
        # • Default Value: 0 (uses the operating system default, which typically enables auto-tuning).
        # This is recommended for most use cases.
        ljm.eWriteNames(self.handle, len(self.input_names), self.input_names, self.voltage_ranges)
        self.actualscanRate.value = ljm.eStreamStart(
            self.handle, SCANS_PER_READ, numAddresses, scan_list, self.attemptedscanRate
        )

        logger.success("started LJM stream on %s", self.handle)

    @ProcessWithCommands.relay_to
    def add_csv(self, path: Path | str) -> None:
        path = Path(path)
        need_header = not path.exists() or path.stat().st_size == 0
        fh = path.open("ab")
        if need_header:
            headers = self.analog_inputs
            if self.digital_inputs:
                headers.append("Digital")
            np.savetxt(fh, np.asarray(headers).reshape(1, len(headers)), fmt="%s", delimiter=",")
        self._labjack_csv_fh = fh
        logger.info("opened %s for writing", path)

    def run(self):
        set_high_prio()
        logger.debug("Start labjack stream.")
        data_1 = None
        data_2 = None
        debounce = 0
        min_off_samples = round(self.attemptedscanRate * 0.01)  # minimum button release duration

        aScanList = ljm.namesToAddresses(len(self.scan_list), self.scan_list)[0]
        if self.digital_inputs or self.extended_inputs:
            aScanList.append(2580)
        logger.debug("ljm: addresses=%s", aScanList)

        while not self._exit_requested:
            if self.handle is None:
                try:
                    self._attempt_connect(aScanList)
                except ljm.ljm.LJMError as err:
                    logger.error("Failed open LJM: %s ; will retry in 1s", err)
                    time.sleep(1)
                    continue

            try:
                data = ljm.eStreamRead(self.handle)
            except ljm.ljm.LJMError as err:
                logger.verbose("ljm.eStreamRead failed: %s", err)
                # if err.errorCode == 1263:  # LJME_NO_RESPONSE_BYTES_RECEIVED
                # ljm.eStreamStop(self.handle)
                self._disconnect()
                ljm.closeAll()
                continue

            self.stream_started.set()

            self.results[:] = np.asarray(data[0])
            if -9999 in self.results:
                logger.warning("ERROR!! OVERFLOW!!")
                # return
                logger.warning("prev data[1]: %s", data_1)
                logger.warning("prev data[2]: %s", data_2)
                logger.warning("data[1]: %s", data[1])
                logger.warning("data[2]: %s", data[2])
                # ljm.eStreamStop(self.handle)
                self._disconnect()
                ljm.closeAll()
                # self._attempt_connect(aScanList)
                continue

            data_1 = data[1]
            data_2 = data[2]
            if int(data[1]) > 48:
                logger.debug("buffer value:  %s", data[1])
            results = self.results.reshape((self.scan_num, SCANS_PER_READ), order="F")

            ints = results[-1].astype(np.uint16)
            new_list = np.unpackbits(ints.view(np.uint8), bitorder="little").reshape(
                16, SCANS_PER_READ, order="F"
            )  # [::-1]

            for button in self.button_list:
                reshape_list = new_list

                self.button_pressed.value = not np.all(reshape_list[button[0]])
                if debounce == 0 and self.button_pressed.value:
                    self.press_counter.value += 1
                    logger.debug("press#: %s", self.press_counter.value)
                    debounce = 1
                if np.all(reshape_list[button[0]][-min_off_samples:]):
                    debounce = 0

            fh = self._labjack_csv_fh
            if fh is not None:
                try:
                    np.savetxt(fh, results.T, fmt="%f", delimiter=",")
                except BaseException as err:
                    self._labjack_csv_fh = None
                    logger.error("could not write to csv file: %s ; closing file", err)
                    fh.close()

            self.graph(results, new_list)  # digital_reshape, extended_reshape)

        fh = self._labjack_csv_fh
        if fh is not None:
            fh.flush()
            fh.close()

        self.stop()

    def graph(self, results: np.ndarray, digital: np.ndarray) -> None:  # , extended):
        new_list = [digital[item] for item in self.digital_inputs]

        new_results = np.vstack((results[:-1], new_list))
        for index, labjack_index in enumerate(self.graph_indices):
            if labjack_index.value == -1:
                self.numpy_arr[index].fill(np.nan)
                continue
            else:
                if labjack_index.value != self.prev_graphs[index]:
                    self.numpy_arr[index].fill(np.nan)

                size = len(new_results[labjack_index.value])
            self.prev_graphs[index] = labjack_index.value
        graph_list_index = 0

        for index, labjack_index in enumerate(self.graph_indices):
            size = len(new_results[labjack_index.value])
            self.numpy_arr[index] = np.roll(self.numpy_arr[index], size)
            self.numpy_arr[index][:size] = np.flip(np.asarray(new_results[labjack_index.value]))
            self.prev_graphs[index] = labjack_index.value
            graph_list_index += 1
        for index, constants_index in enumerate(self.constants):
            size = len(new_results[constants_index])
            self.numpy_arr[graph_list_index] = np.roll(self.numpy_arr[graph_list_index], size)
            self.numpy_arr[graph_list_index][:size] = np.flip(
                np.asarray(new_results[constants_index])
            )
            graph_list_index += 1

        flat = self.numpy_arr.flatten()
        np.frombuffer(self.graph_arr.get_obj(), dtype=ctypes.c_double).reshape(len(flat))[:] = flat

    def stop(self):
        self._disconnect()
        ljm.closeAll()
        self.numpy_arr[:] = np.nan
