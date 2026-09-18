import platform


if platform.system() == "Windows":
    import win32api
    import win32process
    import win32con
    import pywintypes
    import win32file
else:
    win32api = win32process = win32con = pywintypes = win32file = None
