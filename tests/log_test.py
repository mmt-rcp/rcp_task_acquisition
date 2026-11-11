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
)
from rcp_task_acquisition.utils.multiprocess import ProcessWithLogging


class WithLogProc(ProcessWithLogging):
    def run(self):  # noqa
        logger = get_verbose_logger("some_logger_name")
        message_to_pass = self._args[0]
        logger.info("WithLogProc: %s", message_to_pass)


class MultiProcWithLog(multiprocessing.Process):
    def run(self):
        out_log_path, mp_ctx, message_to_pass, subcls = self._args  # noqa
        self.some_target(out_log_path, mp_ctx, message_to_pass, subcls)

    def some_target(self, out_log_path, mp_ctx, message_to_pass, subcls):
        setup_logging(multiprocess_enabled=True)
        log_q_listener = get_log_queue_listener()
        assert log_q_listener is not None
        log_q_listener.add_file_handler(out_log_path)
        p = subcls(args=(message_to_pass,))
        p.start()
        p.join()
        log_q_listener.stop()  # don't forget !
        assert p.exitcode == 0


@pytest.mark.parametrize("start_method", ["spawn", "fork"])
def test_multiproc_log(tmp_path, start_method):
    if start_method == "fork" and platform.system() == "Windows":
        pytest.xfail(reason="Windows does not support multiprocessing fork")
    out_log_path = tmp_path.joinpath("out.log")
    message_to_pass = "some message to pass"
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""
        import sys, importlib, multiprocessing
        out_log_path, start_method, message_to_pass, mod_name, subcls_name = sys.argv[1:]
        multiprocessing.set_start_method(start_method)
        mod = importlib.import_module(mod_name)
        subcls = getattr(mod, subcls_name)
        proc = mod.MultiProcWithLog(args=(out_log_path, start_method, message_to_pass, subcls))
        proc.start()
        proc.join()
        sys.exit(proc.exitcode)
        """),
            out_log_path.as_posix(),
            start_method,
            message_to_pass,
            __name__,
            WithLogProc.__name__,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent,
    )
    out, err = proc.communicate()
    assert proc.returncode == 0, (out, err)
    content = out_log_path.read_text()
    assert f"WithLogProc: {message_to_pass}" in content, content


class NoRunWithLogProc(ProcessWithLogging):
    pass


def test_multiproc_log_no_custom_run(tmp_path):
    out_log_path = tmp_path.joinpath("out.log")
    proc = subprocess.Popen(
        [
            sys.executable,
            "-c",
            textwrap.dedent("""
        import sys, importlib, multiprocessing
        out_log_path, start_method, message_to_pass, mod_name = sys.argv[1:]
        multiprocessing.set_start_method(start_method)
        mod = importlib.import_module(mod_name)
        proc = mod.MultiProcWithLog(args=(out_log_path, start_method, message_to_pass, mod.NoRunWithLogProc))
        proc.start()
        proc.join()
        sys.exit(proc.exitcode)
        """),
            out_log_path.as_posix(),
            "spawn",
            "foobar",
            __name__,
        ],
        stdout=subprocess.PIPE,
        stderr=subprocess.PIPE,
        cwd=Path(__file__).parent,
    )
    out, err = proc.communicate()
    # print(out)
    # print(err)
    assert proc.returncode == 0, (out, err)
    content = out_log_path.read_text()
    assert f"did not declared a target or custom run" in content, content
