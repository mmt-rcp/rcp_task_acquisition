from rcp_task_acquisition.tasks import bases


class CalibrationTask(bases.StimulusBase):
    def __init__(self, base_vars):
        super().__init__(**base_vars)
        self.display.winHandle.set_visible(False)
        self.display.flip()

    def end_stimulus(self) -> None:
        self.display.winHandle.set_visible(True)
        self.display.flip()
