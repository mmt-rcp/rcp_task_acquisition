import os
from pathlib import Path

from rcp_task_acquisition.utils.constants import CODE_DIR

IMG_DIR = Path(CODE_DIR, "tasks", "NaturalisticSpeech", "stimuli")
NON_IMAGE_TASKS = [
    "Personal Narrative-Live Event",
    "Procedural Description-PB&J",
    "Passage Reading-Grandfather",
    "Passage Reading-Rainbow",
]
