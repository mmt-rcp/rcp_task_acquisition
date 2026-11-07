from typing import Any

import numpy as np
from psychopy import core
import pyaudio

from rcp_task_acquisition.tasks import bases
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.typing import TaskMetaData, SharedBool, SharedFloat, SharedInt
from rcp_task_acquisition.tasks.ReachGrasp.constants import (
    MIN_REST_VAL,
    MAX_REST_VAL,
    TRIALS_PER_BLOCK,
    SPACING,
)

logger = get_logger(__name__)


class ReachGrasp(bases.StimulusBase):
    def __init__(
        self,
        base_vars: dict[str, Any],
        grasp: tuple[SharedBool, SharedFloat],
        grasp_count: SharedInt,
    ) -> None:
        super().__init__(**base_vars)
        self.trial_count = 0
        self.hand: str = ""
        self.grasp_object: str = ""
        self.hand_dict: dict[str, str] = {}
        self.grasp_dict: dict[str, str] = {}
        self.grasp_ready = grasp[0]
        self.rest_time = grasp[1]
        self.grasp_count = grasp_count
        self.metadata: dict[str, dict[str, Any]] = {}

    def present(self) -> None:
        self.timer.value = 0
        self.trial_count += 1

        self.grasp_count.value = 0
        self.grasp_ready.value = False
        # timing_list = np.linspace(MIN_REST_VAL, MAX_REST_VAL, TRIALS_PER_BLOCK)
        # np.random.shuffle(timing_list)
        timing_list = self._shuffle_list()
        self.metadata[f"trial_{self.trial_count}"] = {
            "hand": self.hand,
            "grasp_object": self.grasp_object,
            "rest_times": [],
        }

        self.display.switch_patch()
        self.display.draw_patch()
        self.display.flip()
        # self.play_reach_tone()

        gui_clock = core.Clock()
        for rest_value in range(0, TRIALS_PER_BLOCK):
            self.timer.value = int(gui_clock.getTime())
            if self.finish.value == 2:
                self._end_task()
                return

            while not self.grasp_ready.value:
                self.timer.value = int(gui_clock.getTime())
                if self.finish.value == 2:
                    break
            self.metadata[f"trial_{self.trial_count}"]["rest_times"].append(timing_list[rest_value])
            self.grasp_count.value = rest_value  # +1

            self.timer.value = int(gui_clock.getTime())

            # start countdown once hand is resting

            self.grasp_ready.value = False
            clock = core.Clock()
            logger.debug(f"rest_time = {self.rest_time.value}")
            while clock.getTime() < timing_list[rest_value] - self.rest_time.value:
                self.timer.value = int(gui_clock.getTime())
                if self.finish.value == 2:
                    self._end_task()
                    return

            # self.display.draw_patch()
            # self.display.flip()
            # tone to start the reach
            self.play_reach_tone()

        # final wait for participant to touch pad before ending the trial
        while not self.grasp_ready.value:
            self.timer.value = int(gui_clock.getTime())
            if self.finish.value == 2:
                break
        self._end_task()

    def _shuffle_list(self):
        multiplier = int(np.ceil(TRIALS_PER_BLOCK / SPACING))
        timing_list = []

        for x in range(0, multiplier):
            new_list = np.linspace(MIN_REST_VAL, MAX_REST_VAL, SPACING)
            np.random.shuffle(new_list)
            timing_list.extend(list(new_list))
        return timing_list

    def _end_task(self):
        self.display.switch_patch()
        self.display.draw_patch()
        self.display.flip()
        self.play_tone()

    def update_data(self, data: tuple[str, str]) -> None:
        self.hand = data[0]
        self.grasp_object = data[1]

    def saveMetadata(self) -> TaskMetaData:
        return self.metadata

    def play_reach_tone(self, frequency=500, duration=0.25, sample_rate=44100):
        """
        Generates and plays a sine wave tone.
        """
        try:
            # Generate time values
            t = np.linspace(0, duration, int(sample_rate * duration), False)

            # Generate sine wave
            tone = np.sin(frequency * t * 2 * np.pi)

            # Normalize to 16-bit range
            audio = ((tone * 32767) * 0.1).astype(np.int16)

            p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, output=True)
            # Play audio
            stream.write(audio.tobytes())

            # 5. Clean up
            stream.stop_stream()
            stream.close()
            p.terminate()

        except Exception as e:
            logger.error(f"Error generating tone: {e}")
