import serial

from rcp_task_acquisition.utils.constants import BAUDRATE, WRITE_TIMEOUT
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


class SerialDevice:
    def __init__(self):
        self.serSuccess = False
        self.ser: serial.Serial | None = None

    def init_serial(self) -> None:
        ser_dev = None
        for i in range(2, 10):
            port = f"COM{i}"
            try:
                ser_dev = serial.Serial(port, baudrate=BAUDRATE, write_timeout=WRITE_TIMEOUT)
            except Exception as err:
                logger.verbose("Failed tried open serial port %s: %s", port, err)
            else:
                logger.info("Serial connected on port %s", port)
                self.serSuccess = True
                break
        if ser_dev is None:
            logger.error("Serial connection failed")

    def write(self, msg: str | bytes):
        ser_dev = self.ser
        if ser_dev is None:
            logger.warning("Device not connected, skipped write of %r", msg)
            return
        data = msg.encode() if isinstance(msg, str) else msg
        ser_dev.write(data)

    def close(self) -> None:
        ser_dev = self.ser
        if ser_dev is not None:
            ser_dev.close()
            self.ser = None
