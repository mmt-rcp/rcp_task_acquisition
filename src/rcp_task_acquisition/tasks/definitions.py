import dataclasses
import enum

from rcp_task_acquisition.tasks.bases import StimulusBase

from .Diadochokinesis.Diadochokinesis import Diadochokinesis
from .NaturalisticSpeech.NaturalisticSpeech import NaturalisticSpeech
from .NBack.NBack import N_back
from .ReachGrasp.ReachGrasp import ReachGrasp
from .Sara.Sara import Sara
from .ToneTaps.ToneTaps import ToneTapsClosed
from .UpdrsTap.BasicTaps import BasicTaps
from .VerbalFluency.VerbalFluency import VerbalFluency
from .VerbGeneration.VerbGeneration import VerbGeneration
from .VowelSpace.VowelSpace import VowelSpace


@dataclasses.dataclass
class TaskClassConfig:
    code: str
    name: str
    cls: type[StimulusBase]


class TaskItem(
    # TaskClassConfig,
    enum.Enum
):
    # CALIBRATION = TaskClassConfig("calib", "Calibration", Calibration)  # not Stimuli

    DIADOCHOKINESIS = TaskClassConfig("diadochokinesis", "Diadochokinesis", Diadochokinesis)
    NATURALISTIC_SPEECH = TaskClassConfig(
        "naturalistic_speech", "Naturalistic Speech", NaturalisticSpeech
    )
    NBACK = TaskClassConfig("n_back", "Nback", N_back)
    REACH_GRASP = TaskClassConfig("reach_grasp", "Reach Grasp", ReachGrasp)
    SARA = TaskClassConfig("sara", "SARA", Sara)
    TONE_TAPS = TaskClassConfig("tone_taps_closed", "Tone Taps", ToneTapsClosed)
    # UPDRS_TAP = "Updrs Tap"
    VERBAL_FLUENCY = TaskClassConfig("verbal_fluency", "Verbal Fluency", VerbalFluency)
    VERB_GENERATION = TaskClassConfig("verb_generation", "Verb Generation", VerbGeneration)
    VOWEL_SPACE = TaskClassConfig("vowel_space", "Vowel Space", VowelSpace)

    MOTOR_TASK_FINGER_TAPS = TaskClassConfig(
        "motor_task_finger_taps", "Motor Task Finger", BasicTaps
    )
