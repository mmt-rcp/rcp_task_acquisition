import functools

import wx


def call_in_gui(func):
    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        wx.CallAfter(lambda: func(*args, **kwargs))

    return wrapped
