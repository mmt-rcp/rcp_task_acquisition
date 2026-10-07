import ast
import json
import math
import multiprocessing
import time
from enum import Enum
from queue import Empty
from typing import Callable

from rcp_task_acquisition.tasks.bases import StimulusBase
from rcp_task_acquisition.tasks.Diadochokinesis.Diadochokinesis import Diadochokinesis
from rcp_task_acquisition.tasks.HardwareTest import HardwareTest
from rcp_task_acquisition.tasks.NaturalisticSpeech.NaturalisticSpeech import NaturalisticSpeech
from rcp_task_acquisition.tasks.NBack.NBack import N_back
from rcp_task_acquisition.tasks.ReachGrasp.ReachGrasp import ReachGrasp
from rcp_task_acquisition.tasks.Sara.Sara import Sara
from rcp_task_acquisition.tasks.ToneTaps.ToneTaps import ToneTapsClosed
from rcp_task_acquisition.tasks.UpdrsTap.BasicTaps import BasicTaps
from rcp_task_acquisition.tasks.VerbalFluency.VerbalFluency import VerbalFluency
from rcp_task_acquisition.tasks.VerbGeneration.VerbGeneration import VerbGeneration
from rcp_task_acquisition.tasks.VowelSpace.VowelSpace import VowelSpace
from rcp_task_acquisition.utils.displays import Window
from rcp_task_acquisition.utils.logger import get_logger
from rcp_task_acquisition.utils.multiprocess import ProcessWithLogging
from rcp_task_acquisition.utils.run_context import RcpRunContext
from rcp_task_acquisition.utils.typing import SharedBool, SharedEvent, SharedInt

logger = get_logger(__name__)


class Msg(str, Enum):
    INITIALIZE = "init_stimulus"
    UPDATE_TASK = "update_task"
    RUN_TASK = "run_stimulus"
    END_TASK = "end_stimulus"
    ADD_INSTRUCTIONS = "create_instructions"  # unused
    PLAY_INSTRUCTIONS = "play_instructions"
    UPDATE_DATA = "update_data"
    RESET_TASK = "reset_task"
    HARDWARE_TEST = "hardware_test"
    CLOSE_WINDOW = "close"
    VOWEL_SPACE = "vowel_space"
    SEND_METADATA = "send_metadata"


class StimulusThread(ProcessWithLogging):
    def __init__(
        self,
        msgq: multiprocessing.Queue,
        finish: SharedInt,
        shared: SharedInt,
        frame: SharedInt,
        screen_config: int,
        task: str,
        button: SharedBool,
        press_count: SharedInt,
        video_status: SharedInt,
        resultsq: multiprocessing.Queue,
        stimulus_timer: SharedInt,
        event_lock: SharedEvent,
        *,
        rcp_context: RcpRunContext,
    ):
        super().__init__()
        self._rcp_context = rcp_context
        self.msgq = msgq
        self.screenConfig = screen_config
        self.shared = shared
        self.finish = finish
        self.frame = frame
        self.button = button
        # self.stimulusConfig = files.get_stimulus_config("taskconfig.yaml")
        self.totalStimFrames = 0
        self.stimulus: StimulusBase | None = None
        self.resultsq = resultsq
        self.press_count = press_count
        self.video_status = video_status
        self.timer = stimulus_timer
        self.alive = True
        self.task = task
        self.video_lock = event_lock
        self._msg_handlers: dict[Msg, Callable] = {
            Msg.INITIALIZE: self._handle_initialize,
            Msg.SEND_METADATA: self._handle_send_metadata,
            Msg.UPDATE_TASK: self._handle_update_task,
            Msg.UPDATE_DATA: self._handle_update_data,
            Msg.RUN_TASK: self._handle_run_task,
            Msg.RESET_TASK: self._handle_reset_task,
            Msg.END_TASK: self._handle_end_task,
            Msg.VOWEL_SPACE: self._handle_vowel_space,
            Msg.CLOSE_WINDOW: self._handle_close_window,
            Msg.PLAY_INSTRUCTIONS: self._handle_play_instructions,
            Msg.ADD_INSTRUCTIONS: self._handle_add_instructions,
            Msg.HARDWARE_TEST: self._handle_hardware_test,
        }

    def _handle_initialize(self):
        self.params = {}
        self.init_stimuli()

    def _handle_send_metadata(self):
        self.send_metadata()

    def _handle_update_task(self):
        msg = self.msgq.get()
        self.task = msg

    def _handle_update_data(self):
        msgq_data = self.msgq.get()
        logger.debug(f"stim: {msgq_data}")
        try:
            logger.debug(f"stimthread datadata: {msgq_data[0]}")
            if msgq_data[0] == "(":
                trial_data = ast.literal_eval(msgq_data)
            else:
                trial_data = msgq_data
        except Exception as err:
            logger.exception("Cannot evaluate stim thread data: %s", err)
            trial_data = msgq_data
        # trial_data = trial_data.replace("(", "")
        self.stimulus.update_data(trial_data)

    def _handle_run_task(self):
        self.shared.value = 0
        # Main loop for presenting stimuli
        tStart = time.time()
        logger.info(f"Presenting {self.task}")
        if self.shared.value == -1:
            self.alive = False
            return
        self.stimulus.set_first_frame(self.frame.value)
        self.window.reset_stimulus_frame()
        self.stimulus.present()
        self.window.idle(time_list=[])
        self.window.flip()
        self.totalStimFrames += self.window.stimulus_frame
        self.window.reset_stimulus_frame()

        tEnd = time.time()
        tElapsed = tEnd - tStart
        minutes = math.floor(tElapsed / 60)
        seconds = tElapsed % 60
        min_string = f"{math.floor(tElapsed / 60)} minutes, " if minutes > 0 else ""
        logger.info(f"Stimulus protocol completed in {min_string}{seconds:.2f} seconds")
        if self.finish.value != 2:
            self.finish.value = 1
        else:
            self.finish.value = 0

    def _handle_reset_task(self):
        self.stimulus.reset_task()

    def _handle_end_task(self):
        self.end_stimulus()

    def _handle_vowel_space(self):
        results = self.stimulus.get_trial()
        logger.debug(results)
        self.resultsq.put(results)

    def _handle_play_instructions(self):
        msg = self.msgq.get()
        logger.debug(msg)
        self.play_video(msg)

    def _handle_add_instructions(self):
        msg = self.msgq.get()
        self.setup_videos(msg)
        # self.setup_videos(video_filename_dict)

    def _handle_hardware_test(self):
        base_vars = {
            "display": self.window,
            "frame": self.frame,
            "timer": self.timer,
            "video_lock": self.video_lock,
            "video_status": self.video_status,
            "finish": self.finish,
            "rcp_context": self._rcp_context,
        }
        HardwareTest(base_vars).present()

    def _handle_close_window(self):
        self.close_window()

    def run(self):
        try:
            self.window = Window(screen=self.screenConfig, fullScreen=True)
        except Exception as err:
            logger.exception("Could not create window: %s", err)
            self.window = None

        logger.info("entering main loop")
        while self.alive:
            try:
                msg = self.msgq.get(timeout=0.05)
                logger.debug(f"msg: {msg}")
            except Empty:
                continue
            handler = self._msg_handlers.get(msg, None)
            if handler is None:
                logger.warning("Unhandled msg: %s", msg)
                continue
            try:
                handler()
            except SystemExit:
                logger.debug("interrupted stimulus")
                self.end_stimulus()
                # don't see which part of the code is supposed to raise SystemExit to reach here
                # also SystemExit is meant to exit the process. but this is continuing the main loop...
            except Exception as err:
                logger.exception("Error during main loop: %s", err)
                self.end_stimulus()
                break

    def init_stimuli(self):
        base_vars = {
            "display": self.window,
            "frame": self.frame,
            "timer": self.timer,
            "video_lock": self.video_lock,
            "video_status": self.video_status,
            "finish": self.finish,
            "rcp_context": self._rcp_context,
        }
        logger.debug(f"base vars: {base_vars}")
        base_cls = dict(
            n_back=N_back,
            motor_task_finger_taps=BasicTaps,
            naturalistic_speech=NaturalisticSpeech,
            sara=Sara,
            diadochokinesis=Diadochokinesis,
            verbal_fluency=VerbalFluency,
            vowel_space=VowelSpace,
            reach_grasp=ReachGrasp,
            tone_taps_closed=ToneTapsClosed,
            verb_generation=VerbGeneration,
        ).get(self.task, StimulusBase)
        extra_args = []
        if self.task == "n_back":
            extra_args.append(self.button)
        elif self.task == "tone_taps_closed":
            extra_args.append(self.press_count)
        self.stimulus = base_cls(base_vars, *extra_args)
        logger.info(f"stimuli: {self.stimulus}")

    def end_stimulus(self):
        self.window.idle(time_list=[])
        # self.send_metadata()

    def send_metadata(self):
        # logger.debug(f"{self.stimulusConfig}, {self.task}, {self.stimulus}")
        ctx = self._rcp_context
        task_cfg = ctx.tasks_config[self.task]
        results = self.stimulus.saveMetadata(task_cfg, None)  # TODO: not sure what's going on
        json_str = json.dumps(results)
        logger.debug(f"jsonstr: {json_str}")
        self.resultsq.put(json_str)

    def close_window(self):
        self.alive = False
        self.window.close()
        # self.p.join()

    def get_params(self):
        return self.params

    def setup_videos(self, video_filename_dict):
        pass

    def play_video(self, trial: str):
        if self.stimulus is not None:
            self.stimulus.play_instructional_video(trial)
