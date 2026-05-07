import wx
import wx.lib.scrolledpanel as scrolled
import os
from rcp_task_acquisition.models.ParticipantDatabase import ParticipantDatabase
from rcp_task_acquisition.utils.constants import BASEDIR
from rcp_task_acquisition.utils.logger import get_logger
logger = get_logger("./panels/ParticipantPanel") 



class ParticipantPanel():
    def __init__(self, parent=None):
        wx_size = wx.Size(525,250)
        self.metadata = {}
        self.dialog = wx.Dialog(parent, id= wx.ID_ANY, title= 'Add Participant',
                            size = wx_size, pos = wx.DefaultPosition)
        self.panel = scrolled.ScrolledPanel(self.dialog, -1,style=wx.SUNKEN_BORDER)
        self.panel.SetupScrolling(scroll_x=False, scroll_y=False, scrollToTop=False, scrollIntoView=False)
        vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        
        vertical_sizer.Add(self._setup_data(), 0, wx.ALIGN_CENTER_HORIZONTAL| wx.TOP, 15)
        vertical_sizer.Add(self._setup_buttons(), 0, wx.ALIGN_CENTER_HORIZONTAL| wx.TOP, 15)
        self.panel.SetSizerAndFit(vertical_sizer)
    
    
    def _setup_data(self):
        id_text             = wx.StaticText(self.panel, label="Id:")
        self.id_box         = wx.TextCtrl(self.panel, size=wx.Size(150, -1), style=wx.TE_LEFT, value="")
        first_name_text     = wx.StaticText(self.panel, label="First Name:")
        self.first_name_box = wx.TextCtrl(self.panel, size=wx.Size(150, -1), style=wx.TE_LEFT, value="")
        last_name_text      = wx.StaticText(self.panel, label="Last Name:")
        self.last_name_box  = wx.TextCtrl(self.panel, size=wx.Size(150, -1), style=wx.TE_LEFT, value="")
        age_text            = wx.StaticText(self.panel, label="Age:")
        self.age_box        = wx.TextCtrl(self.panel, size=wx.Size(150, -1), style=wx.TE_LEFT, value="")
        diagnosis_text      = wx.StaticText(self.panel, label="Diagnosis:")
        self.diagnosis_box  = wx.TextCtrl(self.panel, size=wx.Size(150, -1), style=wx.TE_LEFT, value="")
        
        row_sizer = wx.GridBagSizer(6, 6)
        row_sizer.Add(id_text,             pos=(0, 0), span=(1,1), flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        row_sizer.Add(self.id_box,         pos=(0, 1), span=(1,2), flag=wx.ALIGN_LEFT | wx.ALL, border=5)
        row_sizer.Add(first_name_text,     pos=(1, 0), span=(1,1), flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        row_sizer.Add(self.first_name_box, pos=(1, 1), span=(1,2), flag=wx.ALIGN_LEFT | wx.ALL, border=5)
        row_sizer.Add(last_name_text,      pos=(1, 3), span=(1,1), flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        row_sizer.Add(self.last_name_box,  pos=(1, 4), span=(1,2), flag=wx.ALIGN_LEFT | wx.ALL, border=5)
        row_sizer.Add(age_text,            pos=(2, 0), span=(1,1), flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        row_sizer.Add(self.age_box,        pos=(2, 1), span=(1,2), flag=wx.ALIGN_LEFT | wx.ALL, border=5)
        row_sizer.Add(diagnosis_text,      pos=(2, 3), span=(1,1), flag=wx.ALIGN_RIGHT | wx.ALL, border=5)
        row_sizer.Add(self.diagnosis_box,  pos=(2, 4), span=(1,2), flag=wx.ALIGN_LEFT | wx.ALL, border=5)
        return row_sizer
        
        
    def _setup_buttons(self):
        
        self.continue_button = wx.Button(self.panel, label="Add Participant", size=wx.Size(100, -1))
        self.cancel_end_button = wx.Button(self.panel, label="Cancel", size=wx.Size(100, -1))
        self.cancel_end_button.Bind(wx.EVT_BUTTON, self.cancel_event)
        self.continue_button.Bind(wx.EVT_BUTTON, self.add_event)
        row_sizer = wx.GridBagSizer(6, 6)
        
        row_sizer.Add(self.continue_button, pos=(0, 0), span=(2,3), flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border=5)
        row_sizer.Add(self.cancel_end_button, pos=(0, 3), span=(2,3), flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border=5)
        return row_sizer
    
    
    def cancel_event(self, event):
        # logger.debug("Cancel Pressed")
        # dlg = wx.MessageDialog(None, 
        #                        "Are you sure you want to delete this session?", 
        #                        "", 
        #                        wx.YES_NO | wx.ICON_QUESTION)
        # if dlg.ShowModal() == wx.ID_NO: 
        #     return
        self.dialog.EndModal(wx.CANCEL)
        self.dialog.Destroy()
    
    def show_error(self):
        self.dialog = wx.MessageDialog(None, 
                               "Participant ID Required", 
                               "", 
                               wx.OK | wx.ICON_WARNING)
        self.dialog.ShowModal()

    
    def add_event(self, event):
        participantDB = ParticipantDatabase()
        database = os.path.join(BASEDIR, "database", "participants.db")
        participantDB.connect(database)
        
        participant_id = self.id_box.GetValue()
        if participant_id == "":
            self.show_error()
            participantDB.close()
            return
        first_name = self.first_name_box.GetValue()
        last_name  = self.last_name_box.GetValue()
        age        = self.age_box.GetValue()
        diagnosis  = self.diagnosis_box.GetValue()
        results = participantDB.add_participant(participant_id,
                                                first_name,
                                                last_name,
                                                age,
                                                diagnosis)
        if not results:
            logger.debug("Error adding participant")
        self.dialog.EndModal(wx.OK)
        self.dialog.Destroy()
        participantDB.close()
        
    
    def show(self):
        return self.dialog.ShowModal()
    



