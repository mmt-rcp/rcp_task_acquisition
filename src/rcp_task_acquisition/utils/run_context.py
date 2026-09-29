import dataclasses
from pathlib import Path

from rcp_task_acquisition.utils import constants, config
from rcp_task_acquisition.utils.config import RcpUserConfig, RcpTasksConfig


@dataclasses.dataclass(kw_only=True)
class _RcpRunContext:
    config_file_path: Path
    user_config: RcpUserConfig
    tasks_config: RcpTasksConfig

    base_dir: Path


@dataclasses.dataclass(kw_only=True)
class RcpRunContext(_RcpRunContext):
    def __init__(
        self,
        *,
        config_file_path: Path,
        user_config: RcpUserConfig,
        tasks_config: RcpTasksConfig,
        base_dir: Path | None = None,
        **kwargs,
    ) -> None:
        if base_dir is None:
            base_dir = constants.BASEDIR
        super().__init__(
            base_dir=base_dir,
            config_file_path=config_file_path,
            user_config=user_config,
            tasks_config=tasks_config,
            **kwargs,
        )
