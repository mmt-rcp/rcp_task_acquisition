import functools
import threading

import wx


def call_in_gui(func):
    """Ensure given function is called within GUI main thread"""

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        if threading.current_thread() is threading.main_thread():
            func(*args, **kwargs)
        else:
            wx.CallAfter(lambda: func(*args, **kwargs))

    return wrapped
