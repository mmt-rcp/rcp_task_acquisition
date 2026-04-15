# -*- coding: utf-8 -*-

import sys
import subprocess
from pathlib import Path
from utils.logger import get_logger
logger = get_logger("./models/StimulusThread") 


top_dir = Path(__file__).parent.parent.resolve()


def _get_from_setuptools_scm():

    out = subprocess.check_output([sys.executable, '-m', 'setuptools_scm'], cwd=top_dir)

    out = out.decode().strip()
    return out if len(out) > 0 else None


__version__ = _get_from_setuptools_scm()


if __version__ == None:
    logger.warning("Cannot find release version")
    __version__= "0.0.0"
