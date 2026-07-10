from multiprocessing import Process
import numpy as np
import ctypes
import win32api,win32process,win32con
import time

from labjack import ljm
from rcp_task_acquisition.utils.constants import (SCANS_PER_READ,
                                                  REBOOT_ADDRESS, 
                                                  OVERFLOW_VALUE)
from rcp_task_acquisition.utils.logger import get_logger
logger = get_logger("./models/LabjackProcess") 


class LabJackDataStream(Process):
    def __init__(self, 
                 finish, 
                 labjack_arr, 
                 create_csv, 
                 labjack_queue, 
                 labjack_list, 
                 graph_indices, 
                 button_pressed, 
                 inputs, 
                 button_list, 
                 press_counter,
                 constants, 
                 voltage_ranges, 
                 stream_started, 
                 scan_rate):
        super().__init__()
        self.attemptedscanRate = 40000
        self.button_pressed = button_pressed
        self.press_counter = press_counter
        self.analog_inputs  = inputs[0]
        self.digital_inputs = inputs[1]
        self.extended_inputs = inputs[2]
        self.stream_started = stream_started
        self.actualscanRate = scan_rate
        self.scan_list = self.analog_inputs
        self.scan_num = len(self.scan_list) 
        self.graph_arr = labjack_arr
        self.numpy_arr = np.empty((6, self.attemptedscanRate*2))
        self.numpy_arr.fill(np.nan)
        self.finished = finish
        self.create_csv = create_csv
        self.labjack_queue = labjack_queue
        self.session_file = ''
        self.labjack_csv= None
        self.graph_indices = graph_indices
        self.prev_graphs = [index.value for index in self.graph_indices]
        self.button_list = button_list
        self.constants = constants
        
        self.voltage_range = {}
        for index, val in enumerate(labjack_list):
            if "A" in val:
                self.voltage_range[val] = voltage_ranges[index]
        logger.debug(self.voltage_range)
        for item in self.extended_inputs:
            self.digital_inputs.append(item+8)
        logger.debug(f"analog: {self.analog_inputs}, digital: {self.digital_inputs}, extended: {self.extended_inputs}")
        if self.digital_inputs:
            self.scan_num+=1
        self.input_names = []
        self.voltage_ranges = []
        for key in self.voltage_range:
            self.input_names.append(f"{key}_RANGE")
            self.voltage_ranges.append(float(self.voltage_range[key][1]))
        self.input_names.append("STREAM_CLOCK_SOURCE")
        self.voltage_ranges.append(0)
        self.results = np.empty(self.scan_num*SCANS_PER_READ)
        self.results.fill(np.nan)
        ljm.closeAll()


    def run(self):
        first_write = True
        logger.debug("Start labjack stream.")
        write_to_csv = False
        prev_device_backlog = None
        prev_ljm_backlog = None
        debounce = 0
        min_off_samples = int(round(self.attemptedscanRate*0.01)) # minimum button release duration
        logger.debug("starting labjack_test")
        try:
            handle = self.open_labjack()
            logger.debug("first_try")
        except:
            try:
                self.retry_labjack()
                logger.debug("first except")
            except:
                self.labjack_queue.put("error")
                return
        self.recover_test(handle)
        
        self.stream_started.value = True
        while not self.finished.value:
            if self.create_csv.value:
                self.labjack_csv = self.labjack_queue.get()
                write_to_csv = True
                self.create_csv.value = False
            data, device_backlog, ljm_backlog = ljm.eStreamRead(handle)
            self.results[:] = np.asarray(data)
            
            if int(OVERFLOW_VALUE) in self.results:
                logger.warn("ERROR! LabJack Overflow!")
                logger.warn(f"prev_device_backlog: {prev_device_backlog}")
                logger.warn(f"prev_ljm_backlog: {prev_ljm_backlog}")
                logger.warn(f"device_backlog: {device_backlog}")
                logger.warn(f"ljm_backlog: {ljm_backlog}")
            prev_device_backlog = device_backlog
            prev_ljm_backlog = ljm_backlog
            if int(device_backlog) > 48:
                logger.debug(f"device buffer value: {device_backlog}")
                
            results = self.results.reshape((self.scan_num, SCANS_PER_READ), order="F")
            ints = results[-1].astype(np.uint16)
            new_list = np.unpackbits(ints.view(np.uint8), bitorder="little").reshape(16, SCANS_PER_READ, order = "F")#[::-1]

            if self.button_list:
                for button in self.button_list:
                    reshape_list = new_list
                    self.button_pressed.value = not np.all(reshape_list[button[0]])
                    if debounce == 0:
                        if self.button_pressed.value:
                            self.press_counter.value += 1
                            logger.debug(f"press#: {self.press_counter.value}")
                            debounce = 1
                    if np.all(reshape_list[button[0]][-min_off_samples:]):
                        debounce = 0
                        
            if write_to_csv:
                self.write_csv( results, first_write)
                first_write = False
            self.graph(results, new_list)         
        self.stop(handle)


    def graph(self, results, digital): 
        new_list = []
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
            self.numpy_arr[graph_list_index][:size] = np.flip(np.asarray(new_results[constants_index]))
            graph_list_index += 1
        np.frombuffer(self.graph_arr.get_obj(), dtype=ctypes.c_double).reshape(len(self.numpy_arr.flatten()))[:] = self.numpy_arr.flatten()


    def write_csv(self, results, write_headers=False): 
        if not self.labjack_csv:
            self.labjack_csv = self.session_file #os.path.join(self.sessionFolder, filename)
        with open(self.labjack_csv, 'ab') as file:
            if write_headers:
                headers = self.analog_inputs
                if self.digital_inputs:
                    headers.append("Digital")
                np.savetxt(file, np.asarray(headers).reshape(1, len(headers)), fmt="%s", delimiter=",")
            np.savetxt(file, results.T, fmt="%f", delimiter=",")
            
            
    def set_folder(self, session_dir):
        self.session_file = session_dir


    def stop(self, handle):
        try:
            ljm.eStreamStop(handle)
        except:
            logger.debug("labjack stream already stopped")
        self.create_csv.value = False
        self.session_file = ""
        self.labjack_csv = ""
        self.numpy_arr[:] = np.nan
        ljm.closeAll()
    

    def retry_labjack(self):
        handle = ljm.openS("ANY", "ANY", "ANY")
        logger.debug("Error opening labjack, retrying")
        try:
            ljm.eWriteName(handle, "SYSTEM_REBOOT", REBOOT_ADDRESS)
            time.sleep(1.5)
            handle = self.open_labjack()
        except:
            ljm.closeAll()
            time.sleep(2.5)
            handle = self.open_labjack()
        

    def open_labjack(self):
        aScanList = ljm.namesToAddresses(len(self.scan_list), self.scan_list)[0]
        if self.digital_inputs or self.extended_inputs:
            aScanList.append(2580)
        logger.debug(aScanList)
        numAddresses  = len(aScanList)
        
        handle = ljm.openS("ANY", "ANY", "ANY")
        ljm.writeLibraryConfigS("LJM_STREAM_TCP_RECEIVE_BUFFER_SIZE", 4194304)
        ljm.eWriteNames(handle, len(self.input_names), self.input_names, self.voltage_ranges)
        self.actualscanRate.value = ljm.eStreamStart(handle, SCANS_PER_READ, numAddresses, aScanList, self.attemptedscanRate)
        return handle
    
        
    def recover_test(self, handle) -> None:
        error_count = 0
        for i in range(2):
            try:
                data, device_backlog, ljm_backlog = ljm.eStreamRead(handle)
                logger.debug(f"{i}: read try")
                break
            except Exception as e:
                error_count += 1
                self.retry_labjack()
                logger.debug(f"{i}: read except {e}")
                
        if error_count >=2:
            logger.debug("queue put error")
            self.labjack_queue.put("error")
        else:
            logger.debug("queue put success")
            self.labjack_queue.put("success")
        
    
    def set_process_priority(self):
        pid = win32api.GetCurrentProcessId()
        process_handle = win32api.OpenProcess(win32con.PROCESS_ALL_ACCESS, True, pid)
        win32process.SetPriorityClass(process_handle, win32process.HIGH_PRIORITY_CLASS)
