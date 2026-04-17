# -*- coding: utf-8 -*-
import wx
from rcp_task_acquisition.panels.SwitchPanel import SwitchPanel
#set up matplotlib to be compatible on commandline/spyder
import matplotlib
matplotlib.use("qtagg")



def run_app():
    app = wx.App()
    main_panel = SwitchPanel()
    app.MainLoop()


if __name__ == '__main__': 
    run_app()

 