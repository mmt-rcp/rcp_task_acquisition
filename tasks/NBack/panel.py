# -*- coding: utf-8 -*-

import wx
# from utils.logging import logger
from datetime import datetime
import logging
from panels.TrialPanel import TrialPanel
from utils.constants import NBACK_TYPES
# Get a logger instance (or the root logger)
logger = logging.getLogger(__name__) # Or logging.getLogger() for the root logger
logger.setLevel(logging.DEBUG)


class NbackPanel(TrialPanel):
    def __init__(self, parent=None):
        super().__init__(parent)
        self.trial_type= "real"
        vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        vertical_sizer.Add(self._setup_nback(), 0, wx.ALIGN_LEFT | wx.ALL, self.border)
        self.SetSizer(vertical_sizer)
        


        
    def _setup_nback(self):
        self.choice_list = ["1-back", "2-back"]
        
        self.practice = wx.RadioButton(self, label="Practice Trial", style= wx.RB_GROUP)
        self.real = wx.RadioButton(self, label="Real Trial")
        # self.practice.Bind(wx.EVT_RADIOBUTTON, self.on_select)
        # self.real.Bind(wx.EVT_RADIOBUTTON, self.on_select)
        
        trial = wx.StaticText(self, label='Select N-back')
        self.nback_choice= wx.Choice(self, 
                                       id=wx.ID_ANY, 
                                       choices=NBACK_TYPES,
                                       size=(200, -1))
        self.nback_choice.SetSelection(0)
        # self.seconds_text = wx.StaticText(self, label= "Rest Time: 0 secs")
        
        text = wx.StaticText(self, label='Select trial type')
        self.continue_button = wx.ToggleButton(self, label="Start Trial")
        # self.continue_button.Bind(wx.EVT_BUTTON, self.continue_event)
        # self.continue_button.Enable(False)
        
        # self.cancel_button = wx.Button(self, label="Finish")
        # # self.cancel_button.Bind(wx.EVT_BUTTON, self.cancel_event)
    
        grid_sizer = wx.GridBagSizer(5, 4)

        grid_sizer.Add(trial, pos=(0, 0), span=(0,2), flag=wx.ALIGN_LEFT | wx.ALL, border=10)
        grid_sizer.Add(self.nback_choice, pos=(0, 2), span=(0,2), flag=wx.ALIGN_LEFT | wx.TOP | wx.BOTTOM, border=10)
        # grid_sizer.Add(self.trial_text, pos=(0, 0), span=(0,4), flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border=10)
        # grid_sizer.Add(hand_text, pos=(1, 0), span=(0,4), flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border=10)
        
        grid_sizer.Add(text, pos=(1, 0), span=(0,4), flag=wx.ALIGN_LEFT | wx.ALL, border=10)
        grid_sizer.Add(self.practice, pos=(2, 0), span=(0,2), flag=wx.ALIGN_LEFT| wx.TOP | wx.BOTTOM, border=10)
        grid_sizer.Add(self.real, pos=(2, 2), span=(0,2), flag=wx.ALIGN_LEFT | wx.TOP | wx.BOTTOM, border=10)
        # grid_sizer.Add(self.seconds_text, pos=(3, 0), span=(0,2), flag=wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, border=20)
        grid_sizer.Add(self.continue_button, pos=(4, 0), span=(0,2), flag=wx.ALIGN_LEFT | wx.TOP, border=10)
        # grid_sizer.Add(self.cancel_button, pos=(4,2), span=(0,2), flag=wx.ALIGN_CENTER_HORIZONTAL | wx.TOP, border=10)  
        return grid_sizer
    
    
    def continue_event(self, event):
        self.rest_timer.Stop()
        # self.EndModal(wx.ID_OK)
        self.selections = {"type": NBACK_TYPES[self.nback_choice.GetSelection()],
                           "trial": self.trial_type}
        self.timestamps[f'{datetime.utcnow().strftime("%Y%m%d%H%M%S")}Z'] = "next_trial_selected"
    
    def update_trial(self, number):
        self.trial_text.SetLabel(f"Selection for Trial # {number}")
        
    def get_result(self):
        self.trial_type = "practice" if self.practice.GetValue() else "real"
        print(f"start:::::::::::::{self.trial_type},{NBACK_TYPES[self.nback_choice.GetSelection()]}")
        return f"{self.trial_type},{NBACK_TYPES[self.nback_choice.GetSelection()]}"
        
    def run_trial(self, number):
        self.nback_choice.Enable(False)
        self.practice.Enable(False)
        # self.continue_button.Enable(False)
        # self.continue_button.Enable(False)
        
        

    def cancel_event(self, event):
        self.cancel = True
        self.rest_timer.Stop()
        
        
    def reset(self, number):
        self.nback_choice.Enable(True)
        self.practice.Enable(True)
        self.continue_button.Enable(True)
        self.continue_button.Enable(True)
        self.continue_button.SetValue(False)
        self.continue_button.SetLabel("Start Trial")
        # self.seconds = 0
        # self.seconds_text.SetLabel(f"Rest Time: {self.seconds} secs")
        # self.continue_button.Enable(False)
        # self.trial_text.SetLabel(f"Selection for Trial # {number}")
    

    def on_timer(self, event):
        self.seconds+=1
        # self.seconds_text.SetLabel(f"Rest Time: {self.seconds} secs")
        # if self.seconds >= 10: