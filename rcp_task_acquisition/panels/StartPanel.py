# -*- coding: utf-8 -*-
import wx
import os


basedir = "/home/rld/task-acquisition/tasks"
imdir = os.path.join(basedir, "PhotoTest_Stimuli")
adult_img = "ADOS_resort.png"
child_img = "park_play.png"

class StartPanel():
    '''
    A pop up that occurs after "start session" is pressed, and occurs after the
    cameras start recording. For almost every task it is just a pop up with an
    "ok".
    For naturalistic speech task allows a user to select a picture for the task.
    
    Attributes:
        task_type (str)
        selection (str | None): name of jpg selected (none) if not naturalistic
                                speech task
    '''
    def __init__(self, task_type=None):
        self.task_type = task_type
        self.selection = None
        
        
    def display(self):
        '''
        Returns:
            return_value (wx flag): wx flag either ok (to continue) or cancel (to exit)

        '''
        return_value = None
        if self.task_type == "naturalistic_speech":
            self.message = self.set_up_photo()
            return_value = self.message.ShowModal()
        
        elif self.task_type == "verbal_fluency":
            self.message= self.set_up_fluency()
            return_value = self.message.ShowModal()

        else:
            self.message = wx.MessageDialog(parent=None,
                                       message="Press Ok to Start Session.",
                                       caption="Start Session",
                                       style=wx.OK | wx.ICON_QUESTION)
            self.message.ShowModal()
            return_value = wx.ID_OK
        self.message.Destroy()
        return return_value

    def set_up_photo(self):
        '''
        Set up the naturalistic speech panel
        Returns:
            message (wx dialog panel)

        '''
        wx_size = wx.Size(450, 300)
        message = wx.Dialog(parent=None, id=wx.ID_ANY, title='Start Trial',
                           size=wx_size, pos=wx.DefaultPosition)
        vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        
        
        adult_image_path = os.path.join(imdir, adult_img)
        adult_image = wx.Image(adult_image_path, wx.BITMAP_TYPE_ANY)
        adult_image = adult_image.Scale(150, 150)
        bitmap = adult_image.ConvertToBitmap()
        # Create a StaticBitmap to display the image
        self.adult_bitmap = wx.StaticBitmap(message, wx.ID_ANY, bitmap)

        child_image_path = os.path.join(imdir, child_img)
        child_image = wx.Image(child_image_path, wx.BITMAP_TYPE_ANY)
        child_image = child_image.Scale(150, 150)
        bitmap = child_image.ConvertToBitmap()
        # Create a StaticBitmap to display the image
        self.child_bitmap = wx.StaticBitmap(message, wx.ID_ANY, bitmap)



        
        photo_text = wx.StaticText(message, label='Choose which photo to show:')
        self.child_photo_button = wx.Button(message, label="Resort", name=adult_img,  size=(150, -1))
        self.child_photo_button.Bind(wx.EVT_BUTTON, self.continue_event)

        self.adult_photo_button = wx.Button(message, label="Park", name=child_img, size=(150, -1))
        self.adult_photo_button.Bind(wx.EVT_BUTTON, self.continue_event)

        self.cancel_button = wx.Button(message, label="Exit", size=(150, -1))
        self.cancel_button.Bind(wx.EVT_BUTTON, self.cancel_event)

        grid_sizer = wx.GridBagSizer(5, 4)

        grid_sizer.Add(photo_text, pos=(0, 0), span=(0, 4),flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border=10)
        
        grid_sizer.Add(self.adult_bitmap, pos=(1, 0), span=(0, 2),  flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=10)
        grid_sizer.Add(self.child_bitmap, pos=(1, 2), span=(0, 2),  flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=10)
        grid_sizer.Add(self.child_photo_button, pos=(2, 0), span=(0, 2), flag=wx.ALIGN_CENTER |  wx.BOTTOM, border=10)
        grid_sizer.Add(self.adult_photo_button, pos=(2, 2), span=(0, 2), flag=wx.ALIGN_CENTER |  wx.BOTTOM, border=10)

        grid_sizer.Add(self.cancel_button, pos=(3, 0), span=(0, 4), flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, border=10)
        
        vertical_sizer.Add(grid_sizer, 0,
                           flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 
                           border=20)
        message.SetSizerAndFit(vertical_sizer)
        return message
    
    def set_up_fluency(self):
        wx_size = wx.Size(450, 300)
        message = wx.Dialog(parent=None, id=wx.ID_ANY, title='Start Trial',
                           size=wx_size, pos=wx.DefaultPosition)
        vertical_sizer = wx.BoxSizer(wx.VERTICAL)
        phonemic_task = wx.StaticText(message, label='Choose Phonemic Category:')
        self.phonemic_list = ['["F", "A", "S"]', '["C", "F", "L"]']
        self.phonemic_choice= wx.Choice(message, 
                                       id=wx.ID_ANY, 
                                       choices=self.phonemic_list,
                                       size=(200, -1))
        semantic_task = wx.StaticText(message, label="Choose Semantic Category:")
        self.semantic_list = ["Animals", "Food and Drink", "Fruits", "Tools"]
        self.semantic_choice= wx.Choice(message, 
                                       id=wx.ID_ANY, 
                                       choices=self.semantic_list,
                                       size=(200, -1))
        
        self.continue_button= wx.Button(message, label="Begin Task", size=(150, -1))
        self.continue_button.Bind(wx.EVT_BUTTON, self.continue_verbal_event)
        
        self.cancel_button = wx.Button(message, label="Exit", size=(150, -1))
        self.cancel_button.Bind(wx.EVT_BUTTON, self.cancel_event)

        grid_sizer = wx.GridBagSizer(5, 6)
        grid_sizer.Add(phonemic_task, pos=(0, 0), span=(0, 2),  flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=10)
        grid_sizer.Add(self.phonemic_choice, pos=(0, 2), span=(0, 4),  flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=10)
        grid_sizer.Add(semantic_task, pos=(1, 0), span=(0, 2),  flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=10)
        grid_sizer.Add(self.semantic_choice, pos=(1, 2), span=(0,4),  flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=10)
        
        grid_sizer.Add(self.continue_button, pos=(2, 0), span=(0, 3),  flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=10)
        grid_sizer.Add(self.cancel_button, pos=(2, 3), span=(0,3),  flag=wx.ALIGN_CENTER_VERTICAL | wx.ALL, border=10)
        vertical_sizer.Add(grid_sizer, 0,
                           flag=wx.ALIGN_CENTER_HORIZONTAL | wx.ALL, 
                           border=20)
        message.SetSizerAndFit(vertical_sizer)
        return message
        
    def cancel_event(self, event):
        logger.debug("Trial Start Cancelled")
        self.message.EndModal(wx.CANCEL)

    def continue_event(self, event):
        self.selection = event.GetEventObject().GetName()
        logger.debug(f"Trial Continued, {self.selection} selected")
        self.message.EndModal(wx.ID_OK)
        
    def continue_verbal_event(self, event):
        self.selection = (self.phonemic_list[self.phonemic_choice.GetSelection()],
                          self.semantic_list[self.semantic_choice.GetSelection()])
        logger.debug(f"Trial Continued, {self.selection} selected")
        print(f"Trial Continued, {self.selection} selected")
        self.message.EndModal(wx.ID_OK)




if __name__ == '__main__':
    app = wx.App()
    metadata_panel = StartPanel("verbal_fluency")
    metadata_panel.display()
    app.MainLoop()