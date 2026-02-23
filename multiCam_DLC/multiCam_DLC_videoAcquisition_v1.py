"""
CLARA toolbox
https://github.com/wryanw/CLARA
W Williamson, wallace.williamson@ucdenver.edu

"""
from multiprocessing import Array, Queue, Value
import wx
import wx.lib.dialogs
import os
import sys
import numpy as np
import time, datetime
import ctypes
import shutil
import queue
from matplotlib.figure import Figure
import matplotlib.patches as patches
from matplotlib.backends.backend_wxagg import FigureCanvasWxAgg as FigureCanvas
import multiCam_DLC.multiCam_DLC_PySpin_v1 as spin
import multiCam_DLC.multiCam_DLC_utils_v2 as clara
import multiCam_DLC.compressVideos_v3 as compressVideos
import utils.auxiliaryfunctions as auxiliaryfunctions
from utils.file_utils import get_stimulus_path, read_config
from models.StimulusThread import StimulusThread
from models.LabjackFrontend import LabjackFrontend
from panels.GraphPanel import GraphPanel
# from panels.FinishSession import FinishSession
from models.Warnings import Warning
# from panels.InterTrialPanel import IntertrialPanel
from panels.MetadataPanel import MetadataPanel
# from utils.logging import logger
from utils.constants import RAW_DATA_DIR
from utils.stimulus_utils import thread_event
from utils.logger import get_logger
logger = get_logger("./multiCam_DLC_videoAcquisition_v1") 
from panels.ControlsPanel import ControlsPanel
import serial
import cv2
# ###########################################################################
# Class for GUI MainFrame
# ###########################################################################

PLOT_LENGTH = 80000

class ImagePanel(wx.Panel):

    def __init__(self, parent, **kwargs):

        wx.Panel.__init__(self, parent, -1,style=wx.SUNKEN_BORDER)
        self.figure = Figure()
        self.canvas = FigureCanvas(self, -1, self.figure)
        self.sizer = wx.BoxSizer(wx.VERTICAL)
        self.sizer.Add(self.canvas, 1, wx.LEFT | wx.TOP | wx.GROW)
        self.SetSizer(self.sizer)
        self.Fit()

    def updateImage(self,  gui_size, axesCt, **kwargs):
        
        # self.figure = Figure()
        self.figure.clf() 
        self.axes = list()
        self.figure.patch.set_facecolor('none')
        if axesCt <= 3:
            if gui_size[0] > gui_size[1]:
                rowCt = 1
                colCt = axesCt
            else:
                colCt = 1
                rowCt = axesCt
        else:
            if gui_size[0] > gui_size[1]:
                rowCt = 2
                colCt = int(np.ceil(axesCt/2))
            else:
                colCt = 2
                rowCt = int(np.ceil(axesCt/2))
        a = 0
        for r in range(int(rowCt)):
            for c in range(int(colCt)):
                self.axes.append(self.figure.add_subplot(rowCt, colCt, a+1, frameon=True))
                
                self.axes[a].set_position([c*1/colCt+0.005,r*1/rowCt+0.005,1/colCt-0.01,1/rowCt-0.01])
        
                self.axes[a].xaxis.set_visible(False)
                self.axes[a].yaxis.set_visible(False)
                a+=1
        
        self.canvas.draw()
        self.Refresh()
        self.Update()
        
        
    def getfigure(self):
        """
        Returns the figure, axes and canvas
        """
        return(self.figure,self.axes,self.canvas)
    

class MainFrame(wx.Frame):
    """Contains the main GUI and button boxes"""
    def __init__(self, parent, task = None):
        self.user_cfg = clara.read_config()
        self.task_cfg = read_config("taskconfig.yaml")
        self.task = None
        self.cam_cfg = {}

        self.hardware_list = [[], [], []] # hardware_lists
        screen_settings = self.user_cfg["screen_settings"]
        # Settting the GUI size and panels design
        displays = (wx.Display(i) for i in range(wx.Display.GetCount())) # Gets the number of displays
        screenSizes = [display.GetGeometry().GetSize() for display in displays] # Gets the size of each display
        #hardcode projector since we will be using the same one 
        logger.debug(f"screenSizes: {screenSizes}")
        index = 0 # For display 1.
        
        screenW = screenSizes[index][0]
        screenH = screenSizes[index][1]
        self.trial_button = None
        self.button_pressed = Value(ctypes.c_bool, False)
        self.recording = False
        self.press_count = Value(ctypes.c_int, 0)
        self.stimulus_panel = Value(ctypes.c_bool, False)
        self.camStrList = list()
        self.slist = list()
        self.master_list = list()
        self.unconnected = list()
        if self.user_cfg['isunconnected']:
            self.unconnected = [str(self.cam_cfg[s]['serial']) for s in self.camStrList]
        else:
            for s in self.cam_cfg:
                if not self.cam_cfg[s]["in_use"]:
                    continue
                if not self.cam_cfg[s]['ismaster']:
                    self.slist.append(str(self.cam_cfg[s]['serial']))
                else:
                    self.master_list.append(str(self.cam_cfg[s]['serial']))
                self.camStrList.append(s)
        
        camCt = len(self.camStrList)
        logger.debug(self.camStrList)
        logger.debug(camCt)
        # logger.debug(str(screenW), " ", str(screenH))
        self.gui_size = (screenW-70, screenH-55)
        # self.gui_size = (1000,1750)
        # self.gui_size = (screenH, screenW-188)
        # if screenW > screenH:
        # #     self.gui_size = (1750, 885)
        #     self.gui_size = (screenW, screenH)
        wx.Frame.__init__ ( self, parent, id = wx.ID_ANY, title = 'Task Master Aquisition',
                            size = wx.Size(self.gui_size), pos = wx.DefaultPosition, style = wx.RESIZE_BORDER|wx.DEFAULT_FRAME_STYLE|wx.TAB_TRAVERSAL )
        # self.Maximize(True)
        self.statusbar = self.CreateStatusBar()
        self.statusbar.SetStatusText("")

        self.SetSizeHints(wx.Size(self.gui_size)) #  This sets the minimum size of the GUI. It can scale now!
        
        ###################################################################################################################################################
        # Spliting the frame into top and bottom panels. Bottom panels contains the widgets. The top panel is for showing images and plotting!
        self.guiDim = 0
        if screenH > screenW:
            self.guiDim = 1
        topSplitter = wx.SplitterWindow(self)
        vSplitter = wx.SplitterWindow(topSplitter)
        self.image_panel = ImagePanel(vSplitter)
        self.image_panel.updateImage(self.gui_size,camCt)
        self.ctrl_panel = GraphPanel(vSplitter, self.gui_size)
        self.widget_panel = ControlsPanel(topSplitter, self.ctrl_panel) #WidgetPanel(topSplitter)
        if self.guiDim == 0:
            vSplitter.SplitHorizontally(self.image_panel, self.ctrl_panel, sashPosition=int(self.gui_size[0]*0.31))
            topSplitter.SplitVertically(vSplitter, self.widget_panel, sashPosition=int(self.gui_size[1]*1.45))
            # vSplitter.SplitVertically(self.image_panel, self.widget_panel, sashPosition=int(self.gui_size[0]*0.775))
            # topSplitter.SplitHorizontally(vSplitter, self.ctrl_panel, sashPosition=int(self.gui_size[1]*0.65))
        else:
            vSplitter.SplitVertically(self.image_panel,self.ctrl_panel, sashPosition=int(self.gui_size[0]*0.75))
            vSplitter.SetSashGravity(0.5)
            self.widget_panel = ControlsPanel(topSplitter, self.ctrl_panel) #WidgetPanel(topSplitter)
            topSplitter.SplitHorizontally(vSplitter, self.widget_panel,sashPosition=int(self.gui_size[1]*0.6))
        topSplitter.SetSashGravity(0.5)
        sizer = wx.BoxSizer(wx.VERTICAL)
        sizer.Add(topSplitter, 1, wx.EXPAND)
        self.SetSizer(sizer)
    

        ###################################################################################################################################################
        # Add Buttons to the WidgetPanel and bind them to their respective functions.
        
        # wSpace = 0
        # wSpacer = wx.GridBagSizer(5, 5)
        (self.init,self.reset,self.update_settings,self.play,self.rec,
        self.exposure_button,self.set_crop,self.crop, self.minRec,self.secRec) = self.widget_panel.get_cam_handles()
        (self.slider, self.hardware_button, 
         self.task_button,  self.quit) = self.widget_panel.get_task_handles()
        (self.contrast_test, self.focus_test, self.hardware_test_panel) = self.widget_panel.get_hardware_handles()
        self.init.Bind(wx.EVT_TOGGLEBUTTON, self.initCams)
        self.update_settings.Bind(wx.EVT_BUTTON, self.updateSettings)
        self.play.Bind(wx.EVT_TOGGLEBUTTON, self.liveFeed)
        self.hardware_button.Bind(wx.EVT_TOGGLEBUTTON, self.liveFeed)
        self.rec.Bind(wx.EVT_TOGGLEBUTTON, self.recordCam)
        self.exposure_button.Bind(wx.EVT_BUTTON, self.get_exposure)
        self.task_button.Bind(wx.EVT_TOGGLEBUTTON, self.run_task)
        # self.quit.Bind(wx.EVT_BUTTON, self.quitButton)
        self.cam_test = Value(ctypes.c_bool, False)
        self.hardware_test = False
        self.liveTimer = wx.Timer(self, wx.ID_ANY)
        self.focus_test.Bind(wx.EVT_TOGGLEBUTTON, self.set_focus)
        self.contrast_test.Bind(wx.EVT_TOGGLEBUTTON, self.set_contrast)
        # self.stimTimer = wx.Timer(self, wx.ID_ANY)
        # self.Bind(wx.EVT_TIMER, self.stimMonitor, self.stimTimer)
 
        self.recTimer = wx.Timer(self, wx.ID_ANY)
        self.shuffle = 1
        self.trainingsetindex = 0
        self.currAxis = 0
        self.x1 = 0
        self.y1 = 0
        self.im = list()
        
        self.figure,self.axes,self.canvas = self.image_panel.getfigure()
        
        #labjack setup
        
        self.ctrl_panel.create_plot(PLOT_LENGTH)
        self.labjack_stream_button = self.ctrl_panel.get_graph_button()
        self.labjack_choices = self.ctrl_panel.get_graph_choices()
        
        self.labjack_timer = wx.Timer(self, wx.ID_ANY)
        self.lj = LabjackFrontend(PLOT_LENGTH, 
                                  self.ctrl_panel, 
                                  self.labjack_timer, 
                                  self.hardware_list,
                                  self.button_pressed,
                                  self.press_count,
                                  self.cam_test)
        
        self.Bind(wx.EVT_TIMER, self.lj.labjack_event, self.labjack_timer)
        self.labjack_stream_button.Bind(wx.EVT_TOGGLEBUTTON, self.lj.labjack_stream)
        

        
        self.im = list()
        self.frmDims = [0,540,0,720]
        self.camIDlsit = list()
        self.shared = Value(ctypes.c_byte, 0)
        self.dlc = Value(ctypes.c_byte, 0)
        self.camaq = Value(ctypes.c_byte, 0)
        self.frmaq = Value(ctypes.c_int, 0)
        self.com = Value(ctypes.c_int, 0)
        self.dir = Value(ctypes.c_int, 0)
        self.dir.value = 1
        self.dlc_frmct = 5
        # self.pLoc = list()
        self.croprec = list()
        self.croproi = list()
        self.frame = list()
        self.frameBuff = list()
        self.dtype = 'uint8'
        self.array = list()
        self.frmGrab = list()
        self.size = self.frmDims[1]*self.frmDims[3]*3
        self.shape = [self.frmDims[1], self.frmDims[3],3]
        frame = np.zeros(self.shape, dtype='ubyte')
        frameBuff = np.zeros(self.size, dtype='ubyte')
        self.cropPts = list()    
        self.pX = list()
        self.pY = list()
        self.pA = list()
        self.array4feed = list()
        for ndx, s in enumerate(self.camStrList):
            self.camIDlsit.append(str(self.cam_cfg[s]['serial']))
            self.croproi.append(self.cam_cfg[s]['crop'])
            self.array4feed.append(Array(ctypes.c_ubyte, self.size))
            self.frmGrab.append(Value(ctypes.c_byte, 0))
            self.frame.append(frame)
            self.frameBuff.append(frameBuff)
            self.im.append(self.axes[ndx].imshow(self.frame[ndx])) # ,cmap='gray'
            self.im[ndx].set_clim(0,255)
            self.points = [-10,-10,1.0]
            
            cpt = self.croproi[ndx]
            self.cropPts.append(cpt)
            rec = [patches.Rectangle((cpt[0],cpt[2]), cpt[1], cpt[3], fill=False, ec = [0.25,0.25,0.75], linewidth=2, linestyle='-',alpha=0.0)]
            self.croprec.append(self.axes[ndx].add_patch(rec[0]))
                
            self.pX.append(Value(ctypes.c_int, 0))
            self.pY.append(Value(ctypes.c_int, 0))
            self.pA.append(Value(ctypes.c_double, 1.0))
            
        self.figure.canvas.draw()
        
        self.alpha = 1
        
        self.canvas.mpl_connect('button_press_event', self.onClick)
        self.Bind(wx.EVT_CHAR_HOOK, self.OnKeyPressed)
        self.exit_stimulus = False
        
        self.warning = Warning()
        #check the display is correct
        #check the correct monitors are displayed
        if wx.Display.GetCount() < 2:
            self.warning.update_error("display")
            self.warning.display()
            sys.exit()

    
        '''
        0-> no video playing
        1-> video playing
        2-> video paused
        3-> video playing from pause
        4-> stop video fully
        5-> video finished run
        '''
        self.video_status = Value(ctypes.c_int, 0)
        self.threads = []
        self.msgq =  queue.Queue()
        self.finish = Value(ctypes.c_byte, 0)
        self.stimulus_time = Value(ctypes.c_double, 0)
        self.time_calculating = Value(ctypes.c_bool, True)
        self.thread = StimulusThread(self.msgq, 
                                     self.finish, 
                                     self.shared, 
                                     self.frmaq, 
                                     self.stimulus_time, 
                                     self.time_calculating, 
                                     screen_settings, 
                                     self.task, 
                                     self.button_pressed,
                                     self.stimulus_panel,
                                     self.press_count,
                                     self.video_status)
        self.startingSession = False
        self.rest_timer = wx.Timer(self)
        
        self.Bind(wx.EVT_TIMER, self.update_intertrial, self.rest_timer)
        
        self.thread.start()
        # self.stimTimer.Start(1000)
        self.save_session = False
        self.count = 0
        self.results_list = []

        
        
    
    def run_task(self, event):
        if self.task_button.GetValue():
            self.trial_dict = {}
            self.start_time= str(f'{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}Z') 
            self.count = 0
            self.thread.reset_count()
            self.finish.value = 0
            self.msgq.put("init_stimulus")
            self.create_file()
            is_success = self.lj.start_labjack()
            # self.count = 0
            self.rest_timer.Start(1000)
            # if there is an error in the labjack that cannot be fixed
            if not is_success:
                self.task_button.SetValue(False)
                return
            
            self.labjack_stream_button.SetValue(True)
            self.labjack_stream_button.Enable(False)
            self.labjack_stream_button.SetLabel("Stop Labjack")
            self.date_string = datetime.datetime.utcnow().strftime("%Y%m%d")
            lj_path = os.path.join(self.sess_dir, f"{self.date_string}_{self.user_cfg['unitRef']}_{self.sess_string}_labjack.txt")
            msg = f"P{self.date_string}_{self.user_cfg['unitRef']}_{self.sess_string}x"
            self.lj.add_csv(lj_path, self.serSuccess, self.ser, msg)
            self.startingSession = True
            self.task_button.SetLabel("End Task")
            self.hardware_button.Enable(False)
            if self.task != "verbal_fluency":
                self.setup_videos()
            if self.task == "vowel_space":
                trial, syllable, finish = self.thread.stimulus.get_trial()
                self.trial_panel.repeat = True
                self.trial_panel.update_trial(trial, syllable)
                print("TRIAL: ", trial)
            self.trial_panel.start_new_trial()
            self.trial_panel.show()
        else:
            if self.trial_button.GetValue():
                self.trial_button.SetValue(False)
                self.trial_event(event)
            if self.recording:
                self.stop_recording(event)
            self.video_status.value = 4
            self.task_button.SetLabel("Start Task")
            self.hardware_button.Enable(True)
            self.trial_panel.hide()
            self.msgq.put('end_stimulus')
            self.labjack_scan_rate = self.lj.stop_labjack()
            self.thread.stimulus.close_audio()
            
            self.finish.value = 0
            self.labjack_stream_button.Enable(True)
            if self.labjack_stream_button.GetValue():
                self.labjack_stream_button.SetValue(False)
                self.labjack_stream_button.SetLabel("Stream Labjack")
            self.labjack_stream_button.Enable(True)
            self.end_time= str(f'{datetime.datetime.now().strftime("%Y%m%d%H%M%S")}Z') 
            self.add_metadata()
            self.thread.stimulus.reset_task()
            self.labjack_timer.Start(200)

    
    def trial_event(self, event):
        if self.trial_button.GetValue():
            
            self.count +=1
            self.rest_timer.Start(1000)
            if self.task == "naturalistic_speech":
                self.thread.stimulus.update_data(self.trial_panel.get_result())
                self.trial_panel.run_trial_(self.count)
                self.trial_button.SetLabel("Stop Trial")
                self.start_recording(event)
                self.msgq.put("run_stimulus")
            if self.task == "n_back":
                self.thread.stimulus.update_data(self.trial_panel.get_result())
                self.trial_panel.run_trial(self.count)
                self.trial_button.SetLabel("Stop Trial")
                self.start_recording(event)
                self.msgq.put("run_stimulus")
            elif self.task == "diadochokinesis":
                self.thread.stimulus.update_data(self.trial_panel.get_results())
                self.trial_panel.run_trial()
                self.start_recording(event)
                self.msgq.put("run_stimulus")
            
            elif self.task == "vowel_space":
                print(self.trial_panel.repeat)
                self.thread.stimulus.update_trial(self.trial_panel.repeat)
                trial, syllable, finish = self.thread.stimulus.get_trial()
                print("TRIAL:::::: ", trial)
                self.trial_panel.update_trial(trial, syllable)
                if finish:
                   self.trial_button.Enable(True) 
                self.trial_panel.repeat = False
                self.trial_button.SetLabel("Stop Trial")
                self.trial_panel.repeat_trial.Enable(False)
                self.start_recording(event)
                self.msgq.put("run_stimulus")
                
            elif self.task == "verbal_fluency":
                if self.trial_panel.first:
                    self.count =0
                    self.trial_button.SetLabel("Start Trial")
                    self.trial_panel.switch_panel()
                    self.result = self.trial_panel.get_result()
                    self.thread.stimulus.get_choices(self.result)
                    self.results_list.append(self.result)
                    self.setup_videos()
                    return
                else:
                    self.result = self.trial_panel.get_result()
                    self.thread.stimulus.get_choices(self.result)
                    self.trial_panel.seconds = 60
                    self.start_recording(event)
                    self.msgq.put("run_stimulus")
                    self.trial_panel.start_trial()
                self.trial_button.SetLabel("Stop Trial")
            elif self.task == "reach_grasp":
                self.trial_panel.run_trial(self.count)
                hand, grasp_object = self.trial_panel.get_result()
                self.thread.stimulus.update_values(hand, grasp_object)
                self.trial_button.SetLabel("Stop Trial")
                self.start_recording(event)
                self.msgq.put("run_stimulus")
            elif (self.task == "motor_task_finger_taps" or
                  self.task == "tone_taps"  or
                  self.task == "tone_taps_closed"):
                self.trial_panel.run_trial(self.count)
                self.thread.stimulus.update_hand(self.trial_panel.get_result())
                self.trial_button.SetLabel("Stop Trial")
                self.start_recording(event)
                self.msgq.put("run_stimulus")
                
            else:
                self.trial_panel.run_trial(self.count)
                self.results_list.append(self.trial_panel.get_result())
                self.trial_button.SetLabel("Stop Trial")
                self.start_recording(event)
                self.msgq.put("run_stimulus")
            
        else:
            if (self.task == "naturalistic_speech" or 
                self.task == "reach_grasp"):
                thread_event.set()
            elif self.task == "sara":
                thread_event.set()
                self.trial_panel.show_scoring()
            elif self.task == "vowel_space":
                thread_event.set()
                trial, syllable, finish = self.thread.stimulus.get_trial()
                print("FINISH TRIAL:::: ", trial)
                if finish:
                    self.trial_panel.is_finish()
                    self.trial_button.Enable(False)
                    self.trial_button.SetLabel("Next Trial")
                    self.trial_panel.repeat_trial.Enable(True)    
                    self.trial_panel.repeat_trial.SetValue(False) 
                    self.stop_recording(event)
                    return
                self.trial_panel.repeat_trial.Enable(True)
                self.trial_panel.repeat_trial.SetValue(False)
                
            elif self.task == "verbal_fluency":
                self.finish.value = 2
            self.finish.value = 2
            self.msgq.put("end_stimulus")
            self.stop_recording(event)
            self.trial_button.SetLabel("Begin Trial")
            self.trial_panel.reset(self.count)
            self.trial_panel.end_trial()
        
    def setup_videos(self): 
        video_paths = self.trial_panel.get_instructions()
        self.msgq.put("create_instructions")
        self.msgq.put(video_paths)
        
        
    def repeat_event(self, event):
        self.trial_panel.repeat_event()
        self.trial_event(event)
        

    def update_intertrial(self, event):
        if self.video_status.value == 5:
            self.trial_panel.stop_video()
            self.video_status.value = 0
        
        elif (self.finish.value == 1 and 
        (self.task != "naturalistic_speech" and self.task != "vowel_space")):


            self.stop_recording(event)
            self.trial_panel.reset(self.count)
            self.trial_panel.end_trial()
            self.stimulus_panel.value = False
            self.finish.value = 0
            
                        
            if self.task == "verbal_fluency":
                self.trial_panel.update_values()
                self.trial_button.SetLabel("Start Trial")
                self.trial_button.seconds = 0


    def play_instructions(self, event):
        if event.GetEventObject().GetValue():
            if type(self.trial_panel.get_instructions()) is str:
                result = ""
            else:
                result = self.trial_panel.get_result()
            self.msgq.put("play_instructions")
            self.msgq.put(result)
            self.trial_panel.start_video()
            # self.video_start.SetLabel("Stop Video")
            # self.video_pause.Enable(True)
            self.video_status.value = 1
        else:
            self.video_status.value = 4
            self.trial_panel.stop_video()
        
        
    def pause_instructions(self, event):
        if event.GetEventObject().GetValue():
            self.video_status.value = 2
            self.trial_panel.pause_video()
        else:
            self.video_status.value = 3
            self.trial_panel.resume_video()


    def set_focus(self, event):
        if self.focus_test.GetValue():
            self.contrast_test.Enable(False)
            self.cam_test.value = True
            self.ctrl_panel.plot_hardware(self.cam_tests, 300)
            self.ctrl_panel.setup_test_legend()
        else:
            self.ctrl_panel.remove_hardware()
            self.contrast_test.Enable(True)
            for cam_index in range(len(self.cam_tests)):
                print(cam_index)
                self.cam_tests[cam_index] = np.full(shape=30*2, fill_value=np.nan)
            self.cam_test.value = False
 
    def set_contrast(self, event):
        if self.contrast_test.GetValue():
            self.focus_test.Enable(False)
            self.cam_test.value = True
            self.ctrl_panel.setup_test_legend()
            self.ctrl_panel.plot_hardware(self.contrast_tests, 1)
        else:
            self.ctrl_panel.remove_hardware()
            self.focus_test.Enable(True)
            for cam_index in range(len(self.contrast_tests)):
                self.contrast_tests[cam_index] = np.full(shape=30*2, fill_value=np.nan)
            self.cam_test.value = False
        
        
    def OnKeyPressed(self, event):
        """
        """
        
        keyCode = event.GetKeyCode()
        
        # Save the new ROI parameters
        if keyCode in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER):
            
            # Write the new parameters to the user config file
            if self.set_crop.GetValue():
                ndx = self.axes.index(self.cropAxes)
                s = self.camStrList[ndx]
                self.cam_cfg[s]['crop'] = np.ndarray.tolist(self.croproi[ndx])
            clara.write_config(self.user_cfg)
            
            #
            self.set_crop.SetValue(False)
            self.widget_panel.Enable(True)
            self.play.SetFocus()
            
        # Modify existing ROI parameters
        elif keyCode in (314, 316, 315, 317, 65, 83, 127) and self.set_crop.GetValue() == True:
            if event.GetKeyCode() == 314: #LEFT
                x = -1
                y =  0
                w =  0
                h =  0
                
            elif event.GetKeyCode() == 316: #RIGHT
                x = 1
                y = 0
                w = 0
                h = 0
                
            elif event.GetKeyCode() == 315: #UP
                x =  0
                y = -1
                w =  0
                h =  0
                
            elif event.GetKeyCode() == 317: #DOWN
                x = 0
                y = 1
                w = 0
                h = 0
                
            
            # Increase size
            elif event.GetKeyCode() == 65: #a
                x = -2
                y = +2
                w = +4
                h = +4
                    
            # Decrease size
            elif event.GetKeyCode() == 83: #s
                x = +2
                y = -2
                w = -4
                h = -4
                
            # Reset the ROI 
            # TODO: Implement this feature
            elif event.GetKeyCode() == 127: #DELETE
                pass
            
            #
            ndx = self.axes.index(self.cropAxes)
            self.croproi[ndx][0] += x
            self.croproi[ndx][1] += w
            self.croproi[ndx][2] += y
            self.croproi[ndx][3] += h
            self.drawROI()
                    
        # Any other case
        else:
            event.Skip()
            
        return
            
    def drawROI(self):
        if self.set_crop.GetValue():
            ndx = self.axes.index(self.cropAxes)
            self.croprec[ndx].set_x(self.croproi[ndx][0])
            self.croprec[ndx].set_y(self.croproi[ndx][2])
            self.croprec[ndx].set_width(self.croproi[ndx][1])
            self.croprec[ndx].set_height(self.croproi[ndx][3])
            if not self.croproi[ndx][0] == 0:
                self.croprec[ndx].set_alpha(0.6)
        self.figure.canvas.draw()
        
        
    def onClick(self,event):
        # self.widget_panel.Enable(False)
        # self.user_cfg = clara.read_config()
        if self.set_crop.GetValue():
            self.cropAxes = event.inaxes
            ndx = self.axes.index(event.inaxes)
            s = self.camStrList[ndx]
            self.croproi[ndx] = self.cam_cfg[s]['crop']
            roi_x = event.xdata
            roi_y = event.ydata
            x_center = self.croproi[ndx][1]/2
            y_center = self.croproi[ndx][3]/2
            logger.info(f"x: {roi_x}, y: {roi_y}")
            logger.info(f"dimensions: {self.frmDims}")
            logger.info(f"center x = {x_center}, center y = {y_center}")
            if roi_x < x_center:
                roi_x = x_center
            elif roi_x+x_center > self.frmDims[3]:
                roi_x =  self.frmDims[3] - x_center
            if roi_y < y_center:
                roi_y = y_center
            if roi_y+y_center > self.frmDims[1]:
                roi_y = self.frmDims[1] - y_center
            self.croproi[ndx] = np.asarray([roi_x-self.croproi[ndx][1]/2,self.croproi[ndx][1],
                                            roi_y-self.croproi[ndx][3]/2,self.croproi[ndx][3]], int)
            logger.info(self.croproi)
        self.drawROI()
                
            
    def compressVid(self, event):
        ok2compress = False
        try:
            if not self.mv.is_alive():
                self.mv.terminate()   
                ok2compress = True
            else:
                if wx.MessageBox("Compress when transfer completes?", caption="Abort", style=wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION):
                    while self.mv.is_alive():
                        time.sleep(10)
                    self.mv.terminate()   
                    ok2compress = True
        except:
            ok2compress = True
            
        if ok2compress:
            self.warning.update_error("compress")
            logger.info('\n\n---- Please DO NOT close this GUI until compression is complete!!! ----\n\n')
            self.compressThread = compressVideos.CLARA_compress()
            self.compressThread.start()
            self.compress_vid.Enable(False)
            

    def camReset(self,event):
        self.initThreads()
        self.camaq.value = 2
        self.startAq()
        time.sleep(3)
        self.stopAq()
        self.deinitThreads()
        logger.info('\n*** CAMERAS RESET ***\n')

        
    def liveFeed(self, event):
        clicked_button = event.GetEventObject()
        button_label = clicked_button.GetLabel()
        if button_label == "Abort":
            self.rec.SetValue(False)
            self.recordCam(event)
            
            if wx.MessageBox("Are you sure?", caption="Abort", style=wx.YES_NO | wx.NO_DEFAULT | wx.ICON_QUESTION):
                shutil.rmtree(self.sess_dir)
                time.sleep(5)
            self.play.SetValue(False)
            self.shared.value = -1
        elif self.play.GetValue() == True or button_label == "Hardware Test":
            if button_label == "Hardware Test":
                self.hardware_test = True
                self.hardware_test_panel.Show()
                is_success = self.lj.start_labjack()
                self.msgq.put("hardware_test")
                if not is_success:
                    print("error with labjack")
                self.labjack_stream_button.SetValue(True)
                self.labjack_stream_button.Enable(False)
                self.labjack_stream_button.SetLabel("Stop Labjack")
            if not self.liveTimer.IsRunning():
                self.camaq.value = 1
                self.startAq()
                self.liveTimer.Start(150)
                self.play.SetLabel('Stop')
                self.hardware_button.SetLabel("End Test")
            self.set_crop.Enable(False)
            self.rec.Enable(False)
            self.minRec.Enable(False)
            self.secRec.Enable(False)
            self.update_settings.Enable(False)
        else:
            self.shared.value = -1
            if self.liveTimer.IsRunning():
                self.liveTimer.Stop()
            self.stopAq()
            time.sleep(2)
            self.play.SetLabel('Live')
            self.hardware_button.SetLabel("Hardware Test")
            if self.hardware_test:
                self.cam_test.value = False
                self.hardware_test = False
                self.focus_test.Enable(True)
                self.focus_test.SetValue(False)
                self.contrast_test.SetValue(False)
                self.contrast_test.Enable(True)
                self.set_focus(event)
                self.set_contrast(event)
                
                self.finish.value = 2
                self.hardware_test_panel.Hide()
                self.hardware_test = False
                self.labjack_scan_rate = self.lj.stop_labjack()
                
                self.labjack_stream_button.Enable(True)
                if self.labjack_stream_button.GetValue():
                    self.labjack_stream_button.SetValue(False)
                    self.labjack_stream_button.SetLabel("Stream Labjack")
                self.labjack_stream_button.Enable(True)
                print("done")
            self.set_crop.Enable(True)
            self.rec.Enable(True)
            self.minRec.Enable(True)
            self.secRec.Enable(True)
            self.update_settings.Enable(True)
        
    def vidPlayer(self, event):
        if self.camaq.value == 2:
            return
        for ndx, im in enumerate(self.im):
            if self.frmGrab[ndx].value == 1:
                self.frameBuff[ndx][0:] = np.frombuffer(self.array4feed[ndx].get_obj(), self.dtype, self.size)
                frame = self.frameBuff[ndx][0:self.dispSize[ndx]].reshape([self.h[ndx], self.w[ndx], 3])
                for f in range(3):
                    self.frame[ndx][self.y1[ndx]:self.y2[ndx],self.x1[ndx]:self.x2[ndx],f] = frame[:,:,f]
                im.set_data(self.frame[ndx])
                self.frmGrab[ndx].value = 0
                x = self.pX[ndx].value
                y = self.pY[ndx].value
                pXY = [x+self.croproi[ndx][0], y+self.croproi[ndx][2]]
                if self.hardware_test:
                    # print(self.camStrList[ndx])
                    self.cam_tests[ndx] = np.roll(self.cam_tests[ndx], 1)
                    gray = cv2.cvtColor(frame, cv2.COLOR_BGR2GRAY)
                    laplacian = cv2.Laplacian(gray, cv2.CV_64F)
                    variance = laplacian.var()
                    
                    self.cam_tests[ndx][0] = variance
                    
                    normalized_img = gray / 255.0
                    # Calculate RMS contrast (Standard Deviation)
                    rms = np.std(normalized_img)
                    self.contrast_tests[ndx] = np.roll(self.contrast_tests[ndx], 1)
                    self.contrast_tests[ndx][0] = rms
                    # print("VARIANCE::: ", variance, " :::RMS::: ", rms)
        if self.hardware_test:
            if self.focus_test.GetValue():
                self.ctrl_panel.plot_hardware(self.cam_tests, 300),
            elif self.contrast_test.GetValue():
                self.ctrl_panel.plot_hardware(self.contrast_tests, 1)
        # self.lj.labjack_event(self.ctrl_panel)
        self.figure.canvas.draw()
        
        
    def autoCapture(self, event):
        self.sliderTabs+=self.sliderRate
        msg = '-'
        if (self.sliderTabs > self.slider.GetMax()) and not (msg == 'fail'):
            if not self.warning.get_has_warned():
                self.warning.update_error("stim_time")
                self.warning.display()
        else:
            self.slider.SetValue(round(self.sliderTabs))
            self.vidPlayer(event)
        
        
    def add_metadata(self):
        metadata = MetadataPanel()
        if metadata.show() == wx.ID_OK:
            self.meta,ruamelFile = clara.metadata_template()
            date_string = datetime.datetime.utcnow().strftime("%Y%m%d")
            cameras = {}
            self.meta["actual_scan_rate"]=self.labjack_scan_rate
            for ndx, s in enumerate(self.camStrList):
                # framerate, exposure = self.cam[ndx].get_actual_settings()
                camset = {'serial':self.cam_cfg[s]['serial'],
                      'ismaster':self.cam_cfg[s]['ismaster'],
                      'crop':self.cam_cfg[s]['crop'],
                      'exposure': self.cam_cfg[s]['exposure'],
                      'framerate': self.cam_cfg[s]['framerate'],
                      'bin': self.cam_cfg[s]['bin'],
                      'nickname': self.cam_cfg[s]['nickname'],
                      'actual_framerate': self.rate[ndx],
                      'actual_exposure': self.exposure[ndx]}
                # self.meta[s]=camset
                cameras[s] = camset
            self.meta['cameras'] = cameras
            # self.meta['duration (s)']=totTime
            self.meta['unitRef']=self.user_cfg['unitRef']
            # self.meta['placeholderA']='info'
            # self.meta['placeholderB']='info'
            # self.meta['Designer']='name'
            # self.meta['Task']='none'
            self.meta['Collection']='info'
            self.meta['hardware'] = self.user_cfg['hardware']
            self.meta['screen_settings'] = self.user_cfg['screen_settings']
            meta_name = '%s_%s_%s_metadata.yaml' % (date_string, self.user_cfg['unitRef'], self.sess_string)
            self.metapath = os.path.join(self.sess_dir,meta_name)
    
            self.meta['StartTime']= self.start_time
            self.meta['administrator_id'] = self.launch_args["administrator_id"]
            self.meta["participant_id"] = self.launch_args["participant_id"]
            self.meta["participant_details"] = self.launch_args["participant_detail"]
            
            self.meta['task'] = self.task
            self.meta['task_settings'] = self.task_cfg[self.task]["settings"]
            self.meta['trial_data'] = self.thread.get_params()
            # if self.results_list:
            #     self.meta['trial_data']["hand_used"] = self.results_list
                # self.results_list = []
            if self.task == "verbal_fluency":
                self.meta["trial_data"]["categories"] = self.trial_panel.add_metadata()
            if self.task == "sara":
                self.meta["trial_data"] = self.trial_panel.add_metadata()
            # if self.task == "diadochokinesis":
            #     self.meta["trial_data"]["trials_ran"] = self.trial_panel.trials
            # if self.task != "vowel_space":
            for data in metadata.data:
                self.meta[data] = metadata.data[data]
                # self.meta['params'] = self.thread.params
                logger.debug(data)
            # self.meta['duration (s)']=round(self.meta['duration (s)']*(self.sliderTabs/100))
            self.meta['EndTime']= self.end_time
            clara.write_metadata(self.meta, self.metapath)
        else:
            #remove entire directory
            logger.debug(self.sess_dir)
            shutil.rmtree(self.sess_dir)
            
    
    def create_file(self):
        date_string = datetime.datetime.utcnow().strftime("%Y%m%d")
        self.base_dir = os.path.join(RAW_DATA_DIR, date_string, self.user_cfg['unitRef'])
        if not os.path.exists(self.base_dir):
            os.makedirs(self.base_dir)
        
        prev_expt_list = [name for name in os.listdir(self.base_dir) if name.startswith('session')]
        file_count = len(prev_expt_list)+1
        self.sess_string = '%s%03d' % ('session', file_count)
        self.sess_dir = os.path.join(self.base_dir, self.sess_string)
        if not os.path.exists(self.sess_dir):
            os.makedirs(self.sess_dir)
        
        
    def start_recording(self, event):
            # if int(self.minRec.GetValue()) == 0 and int(self.secRec.GetValue()) == 0:
            #     return
        if self.recording:
            return
        self.recording = True
        liveRate = 100
        self.Bind(wx.EVT_TIMER, self.autoCapture, self.recTimer)
        # if self.startingSession:
            # filename = self.stim_list[self.stim_config.GetSelection()]
            # self.msgq.put(f"get_filename:{filename}")
            # self.msgq.put("init_stimulus")

        totTime = int(self.secRec.GetValue())+int(self.minRec.GetValue())*60
        spaceneeded = 0
        freespace = shutil.disk_usage(self.base_dir)[2]
        for ndx, w in enumerate(self.aqW):
            recSize = w*self.aqH[ndx]*3*self.recSet[ndx]*totTime
            spaceneeded+=recSize
        if spaceneeded > freespace:
            self.warning.update_error("space")
            self.warning.display()
            
        self.slider.SetMax(100)
        self.slider.SetMin(0)
        self.slider.SetValue(0)
        self.sliderTabs = 0
        logger.info(f"Total estimated run time: {totTime}")
        self.sliderRate = 100/(totTime/(liveRate/1000))

            
        for ndx, s in enumerate(self.camStrList):
            camID = str(self.cam_cfg[s]['serial'])
            self.camq[camID].put('recordPrep')
            date_string = datetime.datetime.utcnow().strftime("%Y%m%d")
            name_base = f"{date_string}_{self.user_cfg['unitRef']}_{self.sess_string}_{self.cam_cfg[s]['nickname']}_trial{self.count}" #% (date_string, self.user_cfg['unitRef'], self.sess_string, self.cam_cfg[s]['nickname'])
            path_base = os.path.join(self.sess_dir,name_base)
            self.camq[camID].put(path_base)
            self.camq_p2read[camID].get()
        self.set_crop.Enable(False)
        self.minRec.Enable(False)
        self.secRec.Enable(False)
        self.update_settings.Enable(False)
        
        if not self.recTimer.IsRunning():
            self.camaq.value = 1
            self.startAq()
            self.recTimer.Start(liveRate)
        self.rec.SetLabel('Stop')
        self.play.SetLabel('Abort')

    
    def stop_recording(self,event):
        if not self.recording:
            return
        self.recording = False
        self.shared.value = -1
        if self.recTimer.IsRunning():
            self.recTimer.Stop()
        self.stopAq()
        time.sleep(2)
        
        # ok2move = False
        # try:
        #     if not self.mv.is_alive():
        #         self.mv.terminate()   
        #         ok2move = True
        # except:
        #     ok2move = True
        # if self.play == event.GetEventObject():
        #     ok2move = False
        # if ok2move:
        #     self.mv = clara.moveVids()
        #     self.mv.start()
        
        self.slider.SetValue(0)
        self.rec.SetLabel('Record')
        self.play.SetLabel('Play')
        
        self.set_crop.Enable(True)
        self.minRec.Enable(True)
        self.secRec.Enable(True)
        self.update_settings.Enable(True)

    
    def initThreads(self):
        self.camq = dict()
        self.camq_p2read = dict()
        self.cam = list()
        for ndx, camID in enumerate(self.camIDlsit):
            self.camq[camID] = Queue()
            self.camq_p2read[camID] = Queue()
            self.cam.append(spin.multiCam_DLC_Cam(self.camq[camID], self.camq_p2read[camID],
                                               camID, self.camIDlsit,
                                               self.frmDims, self.dlc_frmct, self.camaq,
                                               self.frmaq, self.array4feed[ndx], self.frmGrab[ndx]))
            self.cam[ndx].start()
        time.sleep(1)
        for cam in self.unconnected:
            self.camq[cam].put('InitC')
            self.camq_p2read[cam].get()
        
        for cam in self.master_list:
            logger.debug(f"master_list {cam}")
            self.camq[cam].put('InitM')
            self.camq_p2read[cam].get()

        for s in self.slist:
            self.camq[s].put('InitS')
            self.camq_p2read[s].get()
            
            
    def deinitThreads(self):
        for n, camID in enumerate(self.camIDlsit):
            self.camq[camID].put('Release')
            self.camq_p2read[camID].get()
            self.camq[camID].close()
            self.camq_p2read[camID].close()
            self.cam[n].terminate()
            
            
    def startAq(self):
        if self.serSuccess:
            msg = 'Sx'
            self.ser.write(msg.encode())
        if self.camaq.value < 2:
            self.camaq.value = 1
        for cam in self.unconnected:
            self.camq[cam].put('Start')
        for cam in self.master_list:
            self.camq[cam].put('Start')
        for s in self.slist:
            self.camq[s].put('Start')
        for cam in self.master_list:
            self.camq[cam].put('TrigOff')
        for cam in self.unconnected:
            self.camq[cam].put('TrigOff')
        
        
    def stopAq(self):
        if self.serSuccess:
            msg = 'Xx'
            self.ser.write(msg.encode())
        error_message = []
        self.camaq.value = 0
        threshold = 10
        for s in self.unconnected:
            logger.debug(f" unconnected: {s}")
            self.camq[s].put('Stop')
            update = self.camq_p2read[s].get()
            if update != "done":
                if int(update) > threshold:
                    error_message.append(f"{update}% of camera frames dropped for {s}")
                self.camq_p2read[s].get()
        for s in self.slist:
            # print(f" secondary: {s}")
            self.camq[s].put('Stop')
            # print("here")
            update = self.camq_p2read[s].get()
            # print(f"update: {update}")
            if update != "done":
                if int(update) > threshold:
                    error_message.append(f"{update}% of camera frames dropped for {s}")
                self.camq_p2read[s].get()
        for cam in self.master_list:
            # print(f" primary: {s}")
            self.camq[cam].put('Stop')
            update = self.camq_p2read[cam].get()
            if update != "done":
                if int(update) > threshold:
                    error_message.append(f"{update}% of camera frames dropped for {cam}")
                self.camq_p2read[cam].get()
        # print("after removal")
        logger.warn(error_message)
        if error_message:
            error = '\n' + '\n'.join(error_message)
            self.warning.update_error("frames", info=error)
            self.warning.display()


        
    def updateSettings(self, event):
        self.user_cfg = clara.read_config()
        self.aqW = list()
        self.aqH = list()
        self.recSet = list()
        for n, camID in enumerate(self.camIDlsit):
                self.camq[camID].put('updateSettings')
                suc_test = self.camq_p2read[camID].get()
                if suc_test == -1:
                    raise ValueError("Cameras unresponsive")
                if self.crop.GetValue():
                    self.camq[camID].put('crop')
                else:
                    self.camq[camID].put('full')
            
                self.recSet.append(self.camq_p2read[camID].get())
                self.aqW.append(self.camq_p2read[camID].get())
                self.aqH.append(self.camq_p2read[camID].get())

                
    def initCams(self, event):
        if self.init.GetValue() == True:
            self.serSuccess = False
            for i in range(10):
                try:
                    self.ser = serial.Serial('/dev/ttyACM'+str(i), baudrate=9600, write_timeout = 0.1)
                    self.serSuccess = True
                    logger.info('Serial connected')
                    break
                except:
                    pass
                if self.serSuccess:
                    break
            if not self.serSuccess:
                logger.info('Serial connection failed')
            self.Enable(False)
            self.initThreads()
            try: 
                self.updateSettings(event)
            except:
                #add wrning?
                logger.info('\nTrying to fix cameras. Please wait...\n')
                self.deinitThreads()
                self.camReset(event)
                self.initThreads()
    
                try:
                    self.updateSettings(event)
                except:
                    #shut down program if camera error
                    self.deinitThreads()
                    self.labjack_scan_rate = self.lj.stop_labjack()
                    # self.stimTimer.Stop()
                    self.warning.update_error("camera")
                    self.warning.display()
                    self.rec.SetValue(False)
                    try:
                        self.thread.close_window()
                    except:
                        logger.debug('no current stimulus thread')
                    self.statusbar.SetStatusText("")
                    self.Destroy()
                    return False

            self.Bind(wx.EVT_TIMER, self.vidPlayer, self.liveTimer)
            self.get_exposure(event)
            self.camaq.value = 1
            self.startAq()
            time.sleep(0.5)
            self.camaq.value = 0
            self.stopAq()
            self.x1 = list()
            self.x2 = list()
            self.y1 = list()
            self.y2 = list()
            self.h = list()
            self.w = list()
            self.dispSize = list()
            for ndx, im in enumerate(self.im):
                self.frame[ndx] = np.zeros(self.shape, dtype='ubyte')
                self.frameBuff[ndx][0:] = np.frombuffer(self.array4feed[ndx].get_obj(), self.dtype, self.size)
                if self.crop.GetValue():
                    # logger.debug(self.croproi[ndx])
                    self.h.append(self.croproi[ndx][3])
                    self.w.append(self.croproi[ndx][1])
                    self.y1.append(self.croproi[ndx][2])
                    self.x1.append(self.croproi[ndx][0])
                    self.set_crop.Enable(False)
                else:
                    self.h.append(self.frmDims[1])
                    self.w.append(self.frmDims[3])
                    self.y1.append(self.frmDims[0])
                    self.x1.append(self.frmDims[2])
                    self.set_crop.Enable(True)

                self.dispSize.append(self.h[ndx]*self.w[ndx]*3)
                self.y2.append(self.y1[ndx]+self.h[ndx])
                self.x2.append(self.x1[ndx]+self.w[ndx])
                
                frame = self.frameBuff[ndx][0:self.dispSize[ndx]].reshape([self.h[ndx], self.w[ndx],3])
                for f in range(3):
                    self.frame[ndx][self.y1[ndx]:self.y2[ndx],self.x1[ndx]:self.x2[ndx],f] = frame[:,:,f]
                # self.frame[ndx][self.y1[ndx]:self.y2[ndx],self.x1[ndx]:self.x2[ndx]] = frame

                im.set_data(self.frame[ndx])
                
                    
                # if not self.croproi[ndx][0] == 0:
                self.croprec[ndx].set_alpha(0.6)

                            
            self.init.SetLabel('Release')
            self.exposure_button.Enable(True)
            self.play.Enable(True)
            self.rec.Enable(True)
            self.minRec.Enable(True)
            self.secRec.Enable(True)
            self.update_settings.Enable(True)
            self.crop.Enable(False)
            self.reset.Enable(False)
            self.Enable(True)
            
            self.task_button.Enable(True)
            self.figure.canvas.draw()
        else:
            self.init.SetLabel('Enable')
            if self.serSuccess:
                self.ser.close()
            if self.rec.GetValue():
                self.rec.SetValue(False) 
                self.recordCam(event)
            if self.play.GetValue():
                self.play.SetValue(False) 
                self.liveFeed(event)
            if self.set_crop.GetValue():
                self.set_crop.SetValue(False)
            for ndx, im in enumerate(self.im):
                self.frame[ndx] = np.zeros(self.shape, dtype='ubyte')
                im.set_data(self.frame[ndx])
                self.croprec[ndx].set_alpha(0)
                self.pLoc[ndx].set_alpha(0)
            
            self.figure.canvas.draw()
            
            self.set_crop.Enable(False)
            self.play.Enable(False)
            self.rec.Enable(False)
            self.minRec.Enable(False)
            self.secRec.Enable(False)
            self.crop.Enable(True)
            self.reset.Enable(True)
            self.update_settings.Enable(False)
            self.deinitThreads()
            # self.session_button.Enable(False)
        return True          
    

    
    def quitButton(self, event):
        """
        Quits the GUI
        """
        logger.info('Close event called')
        try:
            # self.thread.intertrial_panel.destroy()
            self.thread.close_window()
        except:
            logger.debug('no current stimulus thread')
        try:
            if not self.mv.is_alive():
                self.mv.terminate()
            else:
                # warning
                logger.info('File transfer in progress...\n')
                logger.info('Do not record again until transfer completes.\n')
        except:
            pass
        
        self.statusbar.SetStatusText("")
        self.Destroy()


    def get_exposure(self, event): 
        logger.info("Setting Exposure")
        
        for n, camID in enumerate(self.camIDlsit):
            
                # self.camq[camID].put('updateSettings')
                self.camq[camID].put('setExposure')
        self.camaq.value = 1
        self.startAq()
        time.sleep(1)
        self.camaq.value = 0
        self.stopAq()
        for n, camID in enumerate(self.camIDlsit):
            self.camq[camID].put('getExposure')

            actual_rate = self.camq_p2read[camID].get()
            actual_exposure = self.camq_p2read[camID].get()
            self.rate.append(actual_rate)
            self.exposure.append(actual_exposure)
        pass
    
    def hide(self, event):
        self.is_hidden = True
        self.labjack_scan_rate = self.lj.stop_labjack()
        self.rest_timer.Stop()
        self.video_status.value = 4
        if self.recording:
            self.stop_recording(event)
        if self.play.GetValue():
            self.play.SetValue(False)
            self.liveFeed(event)
        if self.rec.GetValue():
            self.rec.SetValue(False)
            self.recordCam(event)
        # If running a task    
        if self.hardware_button.GetValue():
            self.hardware_button.SetValue(False)
            self.liveFeed(event)
        
        
        if self.task_button.GetValue():
            self.task_button.SetValue(False)
            self.run_task(event)
        if self.init.GetValue():
            self.init.SetValue(False)
            self.initCams(event)
        self.Hide()
        return True
        
    def recordCam(self, event):
        if self.rec.GetValue():
            self.start_recording(event)
        else:
            self.stop_recording(event)
        


        
    def show(self, launch_args, event):
        self.recording = False
        self.user_cfg = clara.read_config()
        self.task_cfg = read_config("taskconfig.yaml")
        self.task = launch_args["task"].strip()
        self.thread.task = launch_args["task"].strip()
        self.launch_args = launch_args
        args = {}
        self.is_hidden = True
        
        self.task_metadata = launch_args
        self.cam_cfg = {}
        if not self.task or self.task not in self.task_cfg.keys():
            args = self.user_cfg["hardware"]
            self.cam_cfg = self.user_cfg["cameras"]
            self.widget_panel.show_cams()
            
        else:
            hardware_list = self.task_cfg[self.task]["settings"]
            self.widget_panel.hide_cams()
            for hardware in hardware_list:
                if hardware in self.user_cfg["hardware"].keys():
                    args[hardware] = self.user_cfg["hardware"][hardware]
                elif hardware in self.user_cfg["cameras"].keys():
                    self.cam_cfg[hardware] = self.user_cfg["cameras"][hardware]

        if not args:
            args = self.user_cfg["hardware"]
        if not self.cam_cfg:
            self.cam_cfg = self.user_cfg["cameras"]
        logger.debug(f"args: {args}")
        logger.debug(f"cam: {self.cam_cfg}")
        
        hardware_tuple = [(arg, args[arg]["labjack_input"], args[arg]["graph"], args[arg]["voltage_range"]) for arg in args]
        sorted_hardware = sorted(hardware_tuple, key=lambda item: item[1])
        hardware_lists = list(zip(*sorted_hardware))
        self.hardware_list = hardware_lists
        self.camStrList = list()

        self.slist = list()
        self.master_list = list()
        self.unconnected = list()
        if self.user_cfg['isunconnected']:
            self.unconnected = [str(self.cam_cfg[s]['serial']) for s in self.camStrList]
        else:
            for s in self.cam_cfg:
                if not self.cam_cfg[s]["in_use"]:
                    continue
                if not self.cam_cfg[s]['ismaster']:
                    self.slist.append(str(self.cam_cfg[s]['serial']))
                else:
                    self.master_list.append(str(self.cam_cfg[s]['serial']))
                self.camStrList.append(s)
        
        camCt = len(self.camStrList)
        logger.debug(self.camStrList)
        logger.debug(camCt)
        self.cam_tests = []
        self.contrast_tests = []
        for cam in self.camStrList:
            self.cam_tests.append(np.full(shape=30*2, fill_value=np.nan))
            self.contrast_tests.append(np.full(shape=30*2, fill_value=np.nan))
        self.ctrl_panel.hardware_test(30*2, camCt, self.camStrList)
        self.rate = []
        self.exposure = []
        self.image_panel.updateImage(self.gui_size, camCt)
        self.figure,self.axes,self.canvas = self.image_panel.getfigure()
        self.im = list()
        self.frmDims = [0,540,0,720]
        self.camIDlsit = list()
        self.dir.value = 1
        self.dlc_frmct = 5
        self.pLoc = list()
        self.croprec = list()
        self.croproi = list()
        self.frame = list()
        self.frameBuff = list()
        self.dtype = 'uint8'
        self.array = list()
        self.frmGrab = list()
        self.size = self.frmDims[1]*self.frmDims[3]*3
        self.shape = [self.frmDims[1], self.frmDims[3],3]
        frame = np.zeros(self.shape, dtype='ubyte')
        frameBuff = np.zeros(self.size, dtype='ubyte')
        self.circleH = list()
        self.circleP = list()
        self.markerSize = 6
        self.cropPts = list()    
        self.pX = list()
        self.pY = list()
        self.pA = list()
        self.array4feed = list()
        for ndx, s in enumerate(self.camStrList):
            # print("C: ", ndx, " ", s)
            self.camIDlsit.append(str(self.cam_cfg[s]['serial']))
            self.croproi.append(self.cam_cfg[s]['crop'])
            self.array4feed.append(Array(ctypes.c_ubyte, self.size))
            self.frmGrab.append(Value(ctypes.c_byte, 0))
            self.frame.append(frame)
            self.frameBuff.append(frameBuff)
            self.im.append(self.axes[ndx].imshow(self.frame[ndx])) # ,cmap='gray'
            self.im[ndx].set_clim(0,255)
            self.points = [-10,-10,1.0]
            
            cpt = self.croproi[ndx]
            self.cropPts.append(cpt)
            rec = [patches.Rectangle((cpt[0],cpt[2]), cpt[1], cpt[3], fill=False, ec = [0.25,0.25,0.75], linewidth=2, linestyle='-',alpha=0.0)]
            self.croprec.append(self.axes[ndx].add_patch(rec[0]))
            circle = [patches.Circle((self.points[0], self.points[1]), radius=self.markerSize, fc = None , alpha=0)]
            self.circleH.append(self.axes[ndx].add_patch(circle[0]))
            circle = [patches.Circle((self.points[0], self.points[1]), radius=self.markerSize, fc = None , alpha=0)]
            self.circleP.append(self.axes[ndx].add_patch(circle[0]))
            circle = [patches.Circle((-10, -10), radius=5, fc=[0.8,0,0], alpha=0.0)]
            self.pLoc.append(self.axes[ndx].add_patch(circle[0]))    
            self.pX.append(Value(ctypes.c_int, 0))
            self.pY.append(Value(ctypes.c_int, 0))
            self.pA.append(Value(ctypes.c_double, 1.0))
        self.init.SetValue(True)
        self.widget_panel.update_task(self.task)
        self.trial_panel = self.widget_panel.get_trial_panel()
        self.trial_button = self.trial_panel.continue_button
        self.hardware_test = False
        self.cam_test.value = False
        try:
            self.repeat_button = self.trial_panel.repeat_trial
            self.repeat_button.Bind(wx.EVT_TOGGLEBUTTON, self.repeat_event)
        except:
            pass
        self.trial_button.Bind(wx.EVT_TOGGLEBUTTON, self.trial_event)
        self.initCams(event)
        self.lj.update_hardware(hardware_lists)
        self.trial_count = 0
        self.press_count.value = 0 
        self.labjack_scan_rate = None
        self.video_start, self.video_pause = self.trial_panel.get_video_buttons()
        if self.video_start != None:
            self.video_start.Bind(wx.EVT_TOGGLEBUTTON, self.play_instructions)
            self.video_pause.Bind(wx.EVT_TOGGLEBUTTON, self.pause_instructions)
            if self.task == "diadochokinesis":
                self.trial_panel.syllable_start_video_button.Bind(wx.EVT_TOGGLEBUTTON, self.play_instructions)
                self.trial_panel.syllable_pause_video_button.Bind(wx.EVT_TOGGLEBUTTON, self.pause_instructions)
        self.video_status.value = 0
        self.Show()
        return True
        
        
    