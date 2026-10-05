import typing
from multiprocessing import sharedctypes
from multiprocessing.synchronize import Event

SharedEvent: typing.TypeAlias = Event

SharedInt: typing.TypeAlias = sharedctypes.Synchronized  # [int]
SharedBool: typing.TypeAlias = sharedctypes.Synchronized  # [bool]

SharedArray: typing.TypeAlias = sharedctypes.SynchronizedArray

# getting:
# >   SharedInt = sharedctypes.Synchronized[int]
# E   TypeError: 'type' object is not subscriptable
#
