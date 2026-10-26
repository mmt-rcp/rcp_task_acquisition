from rcp_task_acquisition.panels.TrialPanel import TrialPanel


def get_task_panel_class(task: str):
    match task:
        case "motor_task_finger_taps":
            from rcp_task_acquisition.tasks.UpdrsTap.panel import FingerTapPanel

            return FingerTapPanel
        case "tone_taps":
            from rcp_task_acquisition.tasks.UpdrsTap.panel import FingerTapPanel

            return FingerTapPanel
        case "tone_taps_closed":
            from rcp_task_acquisition.tasks.ToneTaps.panel import ToneTapsClosedPanel

            return ToneTapsClosedPanel
        case "naturalistic_speech":
            from rcp_task_acquisition.tasks.NaturalisticSpeech.panel import NaturalisticSpeechPanel

            return NaturalisticSpeechPanel
        case "diadochokinesis":
            from rcp_task_acquisition.tasks.Diadochokinesis.panel import DdkPanel

            return DdkPanel
        case "vowel_space":
            from rcp_task_acquisition.tasks.VowelSpace.panel import VowelSpacePanel

            return VowelSpacePanel
        case "verbal_fluency":
            from rcp_task_acquisition.tasks.VerbalFluency.panel import VerbalFluencyPanel

            return VerbalFluencyPanel
        case "n_back":
            from rcp_task_acquisition.tasks.NBack.panel import NbackPanel

            return NbackPanel
        case "reach_grasp":
            from rcp_task_acquisition.tasks.ReachGrasp.panel import ReachGraspPanel

            return ReachGraspPanel
        case "sara":
            from rcp_task_acquisition.tasks.Sara.panel import SaraPanel

            return SaraPanel
        case "verb_generation":
            from rcp_task_acquisition.tasks.VerbGeneration.panel import VerbGenerationPanel

            return VerbGenerationPanel
    # eof match.
    if "calibrate" in task:
        from rcp_task_acquisition.tasks.Calibration.panel import CalibrationPanel

        return CalibrationPanel
    else:
        # logger.verbose("using default TrialPanel for task %r", task)
        return TrialPanel
