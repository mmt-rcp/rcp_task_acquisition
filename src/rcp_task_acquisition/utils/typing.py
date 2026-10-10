import typing
from multiprocessing import sharedctypes
from multiprocessing.synchronize import Event

SharedEvent: typing.TypeAlias = Event

SharedInt: typing.TypeAlias = sharedctypes.Synchronized  # [int]
SharedFloat: typing.TypeAlias = sharedctypes.Synchronized  # [float]
SharedBool: typing.TypeAlias = sharedctypes.Synchronized  # [bool]
SharedArray = sharedctypes.SynchronizedArray

# getting:
# >   SharedInt = sharedctypes.Synchronized[int]
# E   TypeError: 'type' object is not subscriptable
#


CropTupleType: typing.TypeAlias = tuple[int, int, int, int]

HardwareListsType: typing.TypeAlias = tuple[
    tuple[str, ...],  # hardware list
    tuple[str, ...],  # labjack list
    tuple[str, ...],  # min max
    tuple[tuple[float, float], ...],  # voltage range
]
