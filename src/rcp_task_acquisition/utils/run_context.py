import dataclasses
from pathlib import Path

from rcp_task_acquisition.utils import constants
from rcp_task_acquisition.utils.config import RcpTasksGroupConfig, RcpUserConfig


@dataclasses.dataclass(kw_only=True)
class RcpRunContext:
    base_dir: Path = constants.REPO_BASE_DIR  # for "database" files, and also default RawDataDir
    # should be todo: put it in user config file

    config_dir: Path = constants.CODE_CONFIG_DIR_PATH

    user_config: RcpUserConfig
    tasks_config: RcpTasksGroupConfig
