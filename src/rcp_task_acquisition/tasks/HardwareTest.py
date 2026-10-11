import time

from psychopy import core

from rcp_task_acquisition.tasks import bases
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


class HardwareTest(bases.StimulusBase):
    def __init__(self, base_vars):
        super().__init__(**base_vars)
        self.flash_time = 5

    def present(self):
        logger.debug("%s: presenting", self.__class__.__name__)
        self.display.switch_patch()
        self.display.draw_patch()
        self.display.flip()
        clock = core.Clock()
        while True:
            logger.debug("loop0")
            while clock.getTime() < self.flash_time:
                logger.debug("loop1")
                self.display.draw_patch()
                self.display.flip()
                if self.finish.value == 2:
                    self.display.switch_patch()
                    self.display.draw_patch()
                    self.display.flip()
                    self.finish.value = 0
                    return
                time.sleep(0.05)
            clock.reset(0)
            self.display.switch_patch()
            self.display.draw_patch()
            while clock.getTime() < self.flash_time:
                logger.debug("loop2")
                self.display.flip()
                if self.finish.value == 2:
                    self.finish.value = 0
                    return
                time.sleep(0.05)
            self.display.switch_patch()
            clock.reset()
            time.sleep(0.05)

    def saveMetadata(self, name, sessionFolder):
        pass
