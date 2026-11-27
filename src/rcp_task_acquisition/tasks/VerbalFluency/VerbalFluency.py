from psychopy import core

from rcp_task_acquisition.tasks import bases
from rcp_task_acquisition.tasks.VerbalFluency.constants import TRIAL_TIME, VERBAL_FLUENCY_PATHS
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.typing import TaskMetaData

logger = get_logger(__name__)


class VerbalFluency(bases.StimulusBase):
    def __init__(self, base_vars: dict) -> None:
        super().__init__(**base_vars)
        self.trial_num = 0
        self.trial_type = ""
        self.trial_name = ""
        self.trial_dict: dict[str, str] = {}
        self.phonemic_list: list[str] = []
        self.semantic: str = ""
        self.trial_word = ""

    def present(self) -> None:
        self.timer.value = 0
        self.trial_num += 1
        self.trial_dict[f"trial_{self.trial_num}"] = self.trial_word

        self.play_tone()
        self.display.switch_patch()
        self.display.draw_patch()
        self.display.flip()

        clock = core.Clock()
        while clock.getTime() < TRIAL_TIME and not self._task_end_requested:
            self.timer.value = int(clock.getTime())
            self.display.draw_patch()
            self.display.flip()
            if self.finish.value == 2:
                break
        self.timer.value = int(clock.getTime())
        self.display.switch_patch()
        self.display.draw_patch()
        self.display.flip()
        self.play_tone()

    def update_data(self, data: str | tuple[str, str, str]) -> None:
        choices = data
        if isinstance(choices, str):
            self.trial_word = choices
            return
        # if len(choices) == 1:
        #     # NB: todo: following code looks unused,
        #     if choices[0] == "None":
        #         return
        #     else:
        #         self.trial_word = choices[0]
        #         return
        phonetic_list, semantic, trial_word = choices
        self.phonemic_list = phonetic_list.split(".")
        self.semantic = semantic
        self.trial_word = trial_word
        self.instructions_dict = VERBAL_FLUENCY_PATHS[phonetic_list]
        self.instructions_dict[semantic] = VERBAL_FLUENCY_PATHS["Semantic"][semantic]
        logger.debug("instructions_dict: %s", self.instructions_dict)

    def get_trial(self) -> tuple[str, str, str]:
        return self.trial_word, self.trial_type, self.trial_name

    def saveMetadata(self) -> TaskMetaData:
        data = {"time_per_trial": TRIAL_TIME, "trials": self.trial_dict}
        return data
