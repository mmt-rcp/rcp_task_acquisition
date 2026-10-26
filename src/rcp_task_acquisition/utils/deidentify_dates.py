import os
import shutil
from datetime import datetime
from pathlib import Path


from rcp_task_acquisition.utils import config, win_os
from rcp_task_acquisition.utils.logger import get_logger

logger = get_logger(__name__)

import rcp_task_acquisition.utils.file_utils as fu


def set_all_times(path: Path, dt):
    logger.debug("set_all_times on %s", path)
    if win_os.win32con is None:
        raise RuntimeError("Cannot yet use elsewhere than on Windows")

    pywintypes = win_os.pywintypes
    win32con = win_os.win32con
    win32file = win_os.win32file

    ts = dt.timestamp()
    os.utime(path, (ts, ts))  # accessed + modified

    wt = pywintypes.Time(dt)  # creation via Windows API
    handle = win32file.CreateFile(
        path.as_posix(),
        win32con.GENERIC_WRITE,
        win32con.FILE_SHARE_READ | win32con.FILE_SHARE_WRITE | win32con.FILE_SHARE_DELETE,
        None,
        win32con.OPEN_EXISTING,
        win32con.FILE_FLAG_BACKUP_SEMANTICS,  # needed to also handle directories
        None,
    )
    try:
        win32file.SetFileTime(handle, wt, wt, wt)  # creation, access, write
    finally:
        handle.close()


class SimpleLCG:
    def __init__(self, seed=12345):
        self.state = seed & 0xFFFFFFFF

    def next_random(self):
        self.state = (1664525 * self.state + 1013904223) & 0xFFFFFFFF
        return self.state

    def pulse_count(self):
        return self.next_random() % 10


class DateDeidentification:
    def __init__(self, user_cfg: config.RcpUserConfig):
        self.config = user_cfg
        self.raw_data_dir = Path(self.config.RawDataDir)
        self.deid_data_dir = Path(os.path.split(self.raw_data_dir)[0], "DeidentifiedDataLocal")

        rand_num_generator = SimpleLCG(seed=12345)
        date_offset_list = [rand_num_generator.pulse_count() for _ in range(6)]
        self.date_offset = int("".join(map(str, date_offset_list)))

        self.deid_metadate = datetime(2000, 1, 1)

    def deidentify_one_session(self, session_path: Path, date_original: str):
        date_ordinal = datetime.strptime(date_original, "%Y%m%d").date().toordinal()
        metafile_paths = list(session_path.glob("*metadata.yaml"))
        if len(metafile_paths) == 0:
            logger.verbose("no metadata.yaml in %s, skipping deidentify", session_path)
            return
        elif len(metafile_paths) > 1:
            logger.warning("multiple metadata file in %s, refusing to guess", session_path)
            return
        metafile_path = metafile_paths[0]
        metadata = fu.read_metadata(metafile_path)
        logger.debug("read %s, keys: %s", metafile_path, tuple(metadata))
        before_fields = list(metadata)
        for f in before_fields:
            if "Time" in f:
                del metadata[f]
        after_fields = list(metadata)
        logger.debug("removed fields: %s", sorted(set(before_fields) - set(after_fields)))
        part_id = metadata.get("participant_id") or ""
        task_part = session_path.parts[-1]
        date_shift = self.date_offset - date_ordinal
        rng = SimpleLCG(seed=date_shift)
        datepad_list = [rng.pulse_count() for _ in range(2)]
        rn = int("".join(map(str, datepad_list)))
        date_deided = str(f"{date_shift}{rn}")

        unit_dirW = Path(self.deid_data_dir, part_id, date_deided, task_part)
        if not unit_dirW.exists():
            unit_dirW.mkdir(parents=True, exist_ok=True)

        replace_str_from = f"_{date_original}_"
        replace_str_to = f"_{date_deided}_"

        metafiles = session_path.glob("*")
        for src in metafiles:
            if src.name.endswith("metadata.yaml"):
                continue
            dst = unit_dirW.joinpath(src.name.replace(replace_str_from, replace_str_to))
            if not dst.is_file() or (os.path.getsize(src) != os.path.getsize(dst)):
                shutil.copyfile(src, dst)
                set_all_times(dst, self.deid_metadate)

        # NB: rewrite the metadata (cleaned), AFTER it's eventually copied
        dst_meta_path = unit_dirW.joinpath(
            metafile_path.name.replace(replace_str_from, replace_str_to)
        )
        fu.write_metadata(metadata, dst_meta_path)
        set_all_times(dst_meta_path, self.deid_metadate)

        # set all intermediate directories, up to and including deid_data_dir
        rel = unit_dirW.relative_to(self.deid_data_dir)
        while True:
            set_all_times(self.deid_data_dir.joinpath(rel), self.deid_metadate)
            rel = rel.parent
            if rel == rel.parent:  # Path(".")
                break
        logger.debug(f"deid_data: {self.deid_data_dir}")

    def deidentify_all_data(self):
        dirlist = []
        prev_date_list = [name for name in os.listdir(self.raw_data_dir)]
        for d in prev_date_list:
            unit_dirR = os.path.join(self.raw_data_dir, d, self.config.unitRef)
            if os.path.exists(unit_dirR):
                prev_expt_list = [name for name in os.listdir(unit_dirR)]
                for s in prev_expt_list:
                    dirlist.append(os.path.join(unit_dirR, s))
                    session_path = Path(unit_dirR, s)
                    self.deidentify_one_session(session_path)


def run_all_dates(user_config: config.RcpUserConfig):
    deidentify = DateDeidentification(user_config)
    deidentify.deidentify_all_data()
    logger.info("Data deidentification done!")
