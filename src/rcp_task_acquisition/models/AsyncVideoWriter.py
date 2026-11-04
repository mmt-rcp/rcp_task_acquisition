import os
import queue
import subprocess
import threading
from pathlib import Path
from queue import Empty, Full, Queue
from threading import Event, Thread
from typing import Any

import cv2
import numpy as np

from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)


class AsyncFFmpegGPUWriter:
    STOP = object()

    def __init__(
        self,
        video_file: str,
        timestamp_file: str,
        fps: float,
        width: int,
        height: int,
        max_queue: int = 512,
        qp: int = 23,
    ):
        self.video_file = video_file
        self.timestamp_file = timestamp_file
        self.fps = fps
        self.width = width
        self.height = height
        self.max_queue = max_queue
        self.qp = qp

        self.q: Queue[Any] = Queue(maxsize=max_queue)
        self.dropped_by_writer = 0
        self.error: BaseException | None = None
        self.ready = threading.Event()
        self.thread = threading.Thread(target=self._worker, daemon=False)
        self.thread.start()
        self.ready.wait()

        if self.error is not None:
            raise self.error

    def write(self, frame_bgr: bytes, frame_id: int, timestamp_delta: float) -> bool:
        try:
            # Must enqueue an owned frame copy unless the producer already copied.
            self.q.put_nowait((frame_bgr, frame_id, timestamp_delta))
            return True
        except Full:
            self.dropped_by_writer += 1
            return False

    def _worker(self) -> None:
        f = None
        ffmpeg_dir: str = (
            f"{(Path(__file__).parent.parent.parent.parent / 'library' / 'ffmpeg' / 'bin')};"
        )
        custom_env = os.environ.copy()
        custom_env["PATH"] = str(ffmpeg_dir) + custom_env.get("PATH", "")
        cmd = [
            "ffmpeg",
            "-y",
            "-f",
            "rawvideo",
            "-pix_fmt",
            "bgr24",
            "-s",
            f"{self.width}x{self.height}",
            "-r",
            str(self.fps),
            "-i",
            "-",
            "-an",
            "-c:v",
            "hevc_nvenc",
            "-preset",
            "p4",
            "-profile:v",
            "main",
            "-pix_fmt",
            "yuv420p",
            "-rc",
            "vbr",
            "-cq",
            str(self.qp),
            "-b:v",
            "0",
            "-movflags",
            "+faststart",
            self.video_file,
        ]

        proc: subprocess.Popen | None = None
        try:
            proc = subprocess.Popen(
                cmd,
                stdin=subprocess.PIPE,
                stdout=subprocess.DEVNULL,
                stderr=subprocess.PIPE,
                bufsize=0,
                env=custom_env,
                shell=True,
            )
            assert proc is not None

            f = open(self.timestamp_file, "w")
            f.write("frame_id,timestamp\n")

            self.ready.set()

            while True:
                try:
                    item = self.q.get(timeout=1)
                except queue.Empty:
                    continue
                if item is self.STOP:
                    self.q.task_done()
                    break
                try:
                    frame_bgr, frame_id, timestamp_delta = item
                    # ffmpeg expects exactly width*height*3 bytes per frame.
                    # proc.stdin.write(frame_bgr.tobytes())
                    # proc.stdin.write(memoryview(frame_bgr))
                    proc.stdin.write(frame_bgr)  # type: ignore
                    f.write(f"{frame_id},{round(timestamp_delta)}\n")
                finally:
                    self.q.task_done()
        except Exception as err:
            logger.exception("Error while processing: %s", err)
            self.ready.set()
        finally:
            if proc is not None and proc.stdin is not None:
                try:
                    proc.stdin.close()
                except Exception:
                    pass

            if proc is not None:
                stderr = proc.stderr.read().decode(errors="replace") if proc.stderr else ""
                ret = proc.wait()
                if ret != 0:
                    logger.error("ffmpeg exited with code %s ; stderr=%s", ret, stderr[-4000:])

            if f is not None:
                f.flush()
                os.fsync(f.fileno())
                f.close()

    def close(self):
        logger.verbose("closing video writer")
        if self.thread.is_alive():
            try:
                self.q.put(self.STOP, timeout=5)
            except Full:
                logger.warning("video writer queue full")
            else:
                self.q.join()
        self.thread.join(timeout=5)
        if self.thread.is_alive():
            logger.warning("writer thread still alive but continuing")
