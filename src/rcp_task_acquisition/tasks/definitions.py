import dataclasses


from rcp_task_acquisition.tasks.bases import StimulusBase


@dataclasses.dataclass
class TaskTrialClassConfig:
    code: str  # current internal code name still used also hard-coded at few places
    name: str  # human displayable name
    path_part: str  # path name part for use in output data
    cls: type[StimulusBase]  # related StimulusBase subclass
