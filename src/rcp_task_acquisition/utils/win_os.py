import platform


def _import():
    if platform.system() == "Windows":
        import pywintypes
        import win32api
        import win32con
        import win32file
        import win32process
    else:
        return (None,) * 5
    return pywintypes, win32api, win32con, win32file, win32process


pywintypes, win32api, win32con, win32file, win32process = _import()
