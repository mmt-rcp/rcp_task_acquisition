import platform

if platform.system() == "Windows":
    import pywintypes
    import win32api
    import win32con
    import win32file
    import win32process
else:
    win32api = win32process = win32con = pywintypes = win32file = None
