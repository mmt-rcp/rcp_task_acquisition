from typing import Any

from psychopy import core

from rcp_task_acquisition.tasks import bases
from rcp_task_acquisition.tasks.UpdrsTap.constants import BASIC_TAPS_PATHS, BASIC_TAPS_TIME
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.typing import TaskMetaData

logger = get_logger(__name__)


class BasicTaps(bases.StimulusBase):
    def __init__(self, base_vars: dict) -> None:
        super().__init__(**base_vars)
        self.trial_count = 0
        self.hand: str = ""
        self.type: str = ""
        self.hand_used: dict[str, dict[str, str]] = {}
        self.instructions_dict = BASIC_TAPS_PATHS

    def present(self) -> None:
        self.trial_count += 1
        self.hand_used[f"trial_{self.trial_count}"] = {"hand": self.hand, "speed": self.type}
        self.timer.value = 0
        self.display.switch_patch()

        self.display.flip()
        self.play_tone()

        clock = core.Clock()
        while clock.getTime() < BASIC_TAPS_TIME:
            self.display.draw_patch()
            self.display.flip()
            if self.finish.value == 2:
                break
            self.timer.value = int(clock.getTime())

        self.display.switch_patch()
        self.display.draw_patch()
        self.display.flip()
        self.play_tone()

    def update_data(self, data: tuple[str, str]) -> None:
        self.hand = data[0]
        self.type = data[1]

    def saveMetadata(self) -> TaskMetaData:
        data = {
            "time_per_trial": BASIC_TAPS_TIME,
            "number_of_trials": self.trial_count,
            "hand_used": self.hand_used,
        }
        return data
