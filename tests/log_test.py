import logging
import multiprocessing
import platform
import subprocess
import sys
import textwrap
from pathlib import Path

import pytest

from rcp_task_acquisition.utils.logging import (
    get_verbose_logger,
    setup_logging,
    get_log_queue_listener,
    PreciseTimeFormatter,
    MULTIPROC_LOG_FORMAT,
    DateTimeFormats,
)
from rcp_task_acquisition.utils.multiprocess import ProcessWithLogging


class WithLogProc(ProcessWithLogging):
    def run(self):  # noqa
        logger = get_verbose_logger("some_logger_name")
        message_to_pass = self._orig_args[0]
        logger.info("WithLogProc: %s", message_to_pass)


class MultiProcWithLog(multiprocessing.Process):
    def run(self):
        out_log_path, mp_ctx, message_to_pass = self._args  # noqa
        setup_logging(multiprocess_enabled=True)
        log_q_listener = get_log_queue_listener()
        assert log_q_listener is not None
        # log_q_listener.set_handler_level("console_handler", logging.INFO)
        log_q_listener.add_file_handler(
            out_log_path,
            formatter=PreciseTimeFormatter(
                MULTIPROC_LOG_FORMAT,
                datefmt=DateTimeFormats.hour_time_precise,
                time_precision=3,
            ),
        )
        p = WithLogProc(args=(message_to_pass,))
        p.start()
        p.join()
        log_q_listener.stop()  # don't forget !
        assert p.exitcode == 0


@pytest.mark.parametrize("start_method", ["spawn", "fork"])
def test_multiproc_log(tmp_path, start_method):
    if start_method == "fork" and platform.system() == "Windows":
        pytest.skip()
    out_log_path = tmp_path.joinpath("out.log")
    message_to_pass = "some message to pass"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""
        import sys, importlib, multiprocessing
        out_log_path, start_method, message_to_pass, mod_name = sys.argv[1:]
        multiprocessing.set_start_method(start_method)
        mod = importlib.import_module(mod_name)
        proc = mod.MultiProcWithLog(args=(out_log_path, start_method, message_to_pass))
        proc.start()
        proc.join()
        sys.exit(proc.exitcode)
        """),
            out_log_path.as_posix(),
            start_method,
            message_to_pass,
            __name__,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent,
    )
    out, err = proc.communicate()
    assert proc.returncode == 0, (out, err)
    content = out_log_path.read_text()
    assert f"WithLogProc: {message_to_pass}" in content, content
