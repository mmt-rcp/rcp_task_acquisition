import functools
import queue
import threading
from typing import Any

from rcp_task_acquisition.utils.logger import get_logger


logger = get_logger(__name__)


class Algo:
    algo_thread_queue: tuple[threading.Thread, queue.Queue | None] = (
        threading.current_thread(),
        None,
    )

    @classmethod
    def start_algo_thread(cls) -> None:
        prev_th, prev_q = cls.algo_thread_queue
        if prev_q is not None:
            if prev_th.is_alive():
                logger.debug("algo_thread_queue is already running, skip start_algo_thread")
                return
            logger.verbose("previous algo thread not alive")
        algo_q: queue.Queue[Any] = queue.Queue(maxsize=32)
        algo_thread = threading.Thread(
            target=cls._run_behavior,
            args=(algo_q,),
            daemon=True,
            name="behavior",
        )
        algo_thread.start()
        cls.algo_thread_queue = (algo_thread, algo_q)

    @classmethod
    def stop_algo_thread(cls) -> None:
        prev_th, prev_q = cls.algo_thread_queue
        if prev_q is None:
            return
        if prev_th.is_alive():
            prev_q.put_nowait(None)
        prev_th.join(5)
        logger.verbose("joined algo thread")
        cls.algo_thread_queue = (threading.main_thread(), None)

    @classmethod
    def put_to(cls, func, args=(), kwargs=None, *, timeout=0) -> None:
        algo_q = cls.algo_thread_queue[1]
        if algo_q is None:
            raise RuntimeError("algo_thread_queue is None")
        raw = (func, args, kwargs)
        try:
            algo_q.put(raw, timeout=timeout)
        except queue.Full:
            logger.error("cannot put %s to behavior thread, queue full")
            raise

    @staticmethod
    def _run_behavior(algo_q) -> None:
        get = algo_q.get
        while True:
            try:
                raw = get(timeout=0.1)
            except queue.Empty:
                continue
            if raw is None:
                logger.info("received None, exiting")
                break
            try:
                func, args, kwargs = raw
            except (TypeError, ValueError):
                logger.error("invalid data")
                continue
            logger.info("executing %s", func.__name__)
            try:
                func(*args) if kwargs is None else func(*args, **kwargs)
            except (KeyboardInterrupt, SystemExit) as err:
                logger.notice("received %s (%r), exiting", err, err)
                break
            except Exception as err:
                logger.exception("error during %s: %s", func.__name__, err)
            else:
                logger.verbose("%s succeeded", func.__name__)


def put_to_algo(func):

    @functools.wraps(func)
    def wrapped(*args, **kwargs):
        Algo.put_to(func, args, kwargs)

    return wrapped
