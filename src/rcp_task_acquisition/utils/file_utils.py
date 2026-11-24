import os
from io import StringIO
from pathlib import Path
from typing import Any

import numpy
import ruamel.yaml.nodes

from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


def represent_numpy_float64(self, value):
    return self.represent_float(value)  # alternatively dump as a tagged float


def represent_numpy_int64(self, value):
    return self.represent_int(value)  # alternatively dump as a tagged int


def represent_numpy_array(self, array, flow_style=None):
    tag = "!numpy.ndarray"
    value = []
    node = ruamel.yaml.nodes.SequenceNode(tag, value, flow_style=flow_style)
    for elem in array:
        node_elem = self.represent_data(elem)
        value.append(node_elem)
    if flow_style is None:
        node.flow_style = True
    return node


yaml = ruamel.yaml.YAML()
# yaml.Representer.add_representer(numpy.ndarray, represent_numpy_array)
# we'll see if we want/need represent numpy array or not.
yaml.Representer.add_representer(numpy.float64, represent_numpy_float64)
yaml.Representer.add_representer(numpy.int64, represent_numpy_int64)


def write_metadata(data: dict[str, Any], file_path: str | Path) -> None:
    file_path = Path(file_path)
    logger.info("writing metadata to %s", file_path)
    dumped = StringIO()
    try:
        yaml.dump(data, dumped)
    except Exception as err:
        logger.error("error serializing data: %s ; data=%s", err, data)
        raise
    raw = dumped.getvalue()
    with file_path.open("w") as fh:
        fh.write(raw)


def metadata_template() -> ruamel.yaml.CommentedMap:
    """
    Creates a template for config.yaml file. This specific order is preserved while saving as yaml file.
    """
    yaml_str = """\
# Version
    version:
    \n
    
# Experiment
    Designer:
    administrator_id:
    Task:
    StartTime_Local:
    StartTime_UTC:
    EndTime_Local:
    EndTime_UTC:
    Collection:
    duration (s):
    unitRef:
    \n

# Participant
    participant_id:
    participant_details:
    \n

# Screen Config
    screen_settings:
    \n

# Task
    task:
    task_settings:
    trial_data:
    task_notes:
    \n

# Cameras
    framerate:
    framerate_decrease_factor:
    cameras:
    \n

# Labjack Settings
    actual_scan_rate:
    hardware:
    \n
"""

    ruamelFile = ruamel.yaml.YAML()
    meta_cfg = ruamelFile.load(yaml_str)
    return meta_cfg


def read_metadata(path: Path) -> ruamel.yaml.CommentedMap:
    logger.debug("reading metadata from %s", path)
    loader = ruamel.yaml.YAML()
    with path.open("r") as f:
        cfg = loader.load(f)
    return cfg
