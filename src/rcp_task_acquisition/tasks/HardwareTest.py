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
        logger.debug("before present loop ; flash=%s clock=%s", self.flash_time, clock.getTime())
        while True:
            p0 = time.perf_counter()
            cnt = -1
            while clock.getTime() < self.flash_time:
                cnt += 1
                # logger.debug("loop1")
                self.display.draw_patch()
                self.display.flip()
                if self.finish.value == 2:
                    self.display.switch_patch()
                    self.display.draw_patch()
                    self.display.flip()
                    self.finish.value = 0
                    return
                # time.sleep(0.05)
            p1 = time.perf_counter()
            loop_dur = p1 - p0
            logger.debug(
                "after present loop0: dur=%.2f cnt=%s (%.2f / s) clock=%s",
                loop_dur,
                cnt,
                cnt / loop_dur,
                clock.getTime(),
            )
            clock.reset(0)
            self.display.switch_patch()
            self.display.draw_patch()
            p0 = time.perf_counter()
            cnt = -1
            while clock.getTime() < self.flash_time:
                cnt += 1
                self.display.flip()
                if self.finish.value == 2:
                    self.finish.value = 0
                    return
                # time.sleep(0.05)
            p1 = time.perf_counter()
            loop_dur = p1 - p0
            logger.debug(
                "after present loop0: dur=%.2f cnt=%s (%.2f / s) clock=%s",
                loop_dur,
                cnt,
                cnt / loop_dur,
                clock.getTime(),
            )
            self.display.switch_patch()
            clock.reset()
            # time.sleep(0.05)
