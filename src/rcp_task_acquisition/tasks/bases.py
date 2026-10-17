import functools
from pathlib import Path
from typing import Any, Literal

import numpy as np
import pandas as pd
import pyaudio
from psychopy import core, visual
from psychopy.visual.vlcmoviestim import VlcMovieStim

from rcp_task_acquisition.utils.constants import (
    DURATION,
    FREQUENCY,
    SAMPLING_RATE,
    VideoStatus,
)
from rcp_task_acquisition.utils.displays import Window
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.run_context import RcpRunContext
from rcp_task_acquisition.utils.typing import SharedEvent, SharedInt, TaskMetaData

logger = get_logger(__name__)


_registered_stimuli_classes: list[type["StimulusBase"]] = []


class StimulusBase:
    def __init_subclass__(cls) -> None:
        super().__init_subclass__()
        _registered_stimuli_classes.append(cls)

    def __init__(
        self,
        display: Window,  # this is the patient monitor window
        frame: SharedInt,
        timer: SharedInt,
        video_lock: SharedEvent,
        *,
        video_status: SharedInt,
        finish: SharedInt,
        rcp_context: RcpRunContext,
    ):
        self._rcp_context = rcp_context
        self.display = display
        self.frame = frame
        self.prev_flip_time: float | None = None
        self.instructions_dict: dict[str, str] = {}
        self.current_trial: str | None = None
        self.video_status = video_status
        self.timer = timer
        self.start_test = False  # unused
        self.finish = finish
        self.trial = 0  # current trial nbr
        self.video_lock = video_lock
        self.first_frame = -1

    def end_stimulus(self):
        """For subclass to customize"""

    def present(self) -> None:
        self.timer.value = 0
        self.trial += 1
        self.play_tone()
        # switch the photodiode patch to be "On" while the photo is being shown
        self.display.switch_patch()
        self.display.draw_patch()
        self.display.flip()
        clock = core.Clock()
        while True:
            if self.finish.value == 2:
                break
            self.timer.value = int(clock.getTime())
        # turn the patch to off and flip the display to black
        self.display.switch_patch()
        self.display.draw_patch()
        self.play_tone()

    def create_csv(self, name, sessionFolder, metadata, start_frame, columns=None) -> None:
        sessionFolderPath = Path(sessionFolder)
        if sessionFolderPath.exists() == False:
            return
        csv_name = sessionFolderPath.joinpath(f"{name}-{int(start_frame)}.csv")

        data = pd.DataFrame(metadata)
        if columns:
            data.columns = columns
        data.to_csv(csv_name, index=False)

    def set_first_frame(self, frame: int) -> None:
        self.first_frame = frame

    def saveMetadata(self) -> TaskMetaData:
        """Returns the stimulus current metadata"""
        return {}

    def play_tone(self):
        # winsound.Beep(int(FREQUENCY), DURATION)
        self.play_stone(FREQUENCY, DURATION, SAMPLING_RATE)

    def reset_task(self):
        # placeholder
        pass

    def play_instructional_video(self, trial_name: str):
        user_cfg = self._rcp_context.user_config
        logger.debug("play_instructional_video: trial name: %r", trial_name)
        file = self.instructions_dict[trial_name]
        path = Path(user_cfg.VideoDir, file)
        if not path.exists():
            logger.error("video at %s does not exist", path)
            self.video_status.value = VideoStatus.ERROR
            return
        logger.debug("playing %s", path)
        video = VlcMovieStim(
            self.display,
            path.as_posix(),
            size=self.display.size,
            pos=[0, 0],
            flipVert=False,
            flipHoriz=False,
            loop=False,
        )

        video.play()
        while video.status != visual.FINISHED:
            vid_status = self.video_status.value  # read shared value once
            if vid_status == VideoStatus.PAUSED:
                video.pause()
            elif vid_status == VideoStatus.START_FROM_PAUSE:
                video.play()
                self.video_status.value = VideoStatus.PLAY
            elif vid_status == VideoStatus.STOP:
                self.video_status.value = VideoStatus.FINISHED
                video.stop()
                self.display.idle(time_list=[])
                self.video_lock.set()
                self.video_lock.clear()
                return
            else:
                # Draw the current frame of the video
                video.draw()
                self.display.flip()

        self.video_status.value = VideoStatus.FINISHED
        video.stop()
        self.display.idle(time_list=[])

    def trial_bookends(self):
        """
        could probably have a better name but I am tired today.
        this is the way most of the task start/end so it saves error by just combining
            them into the same function
        turn the photodiode patch on/off, draw, and play a tone.
        """

        self.display.switch_patch()
        self.display.draw_patch()
        self.display.flip()
        self.play_tone()

    def update_data(self, data):
        pass

    @staticmethod
    @functools.lru_cache(maxsize=64)
    def _make_audio_data(frequency=440, duration=1.0, sample_rate=44100) -> bytes:
        # Generate time values
        t = np.linspace(0, duration, int(sample_rate * duration), False)
        # Generate sine wave
        tone = np.sin(frequency * t * 2 * np.pi)
        # Normalize to 16-bit range
        audio = ((tone * 32767) * 0.1).astype(np.int16)
        return audio.tobytes()

    def play_stone(self, frequency=440, duration=1.0, sample_rate=44100):
        """
        Generates and plays a sine wave tone.
        """
        try:
            data = self._make_audio_data(frequency, duration, sample_rate)
            p = pyaudio.PyAudio()
            stream = p.open(format=pyaudio.paInt16, channels=1, rate=sample_rate, output=True)
            # Play audio
            stream.write(data)
            # 5. Clean up
            stream.stop_stream()
            stream.close()
            p.terminate()
            # play_obj = sima.play_buffer(audio, 1, 2, sample_rate)
            # play_obj.wait_done()
        except Exception as err:
            logger.exception("Error generating tone: %s", err, stacklevel=3)
