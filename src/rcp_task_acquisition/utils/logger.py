from rcp_task_acquisition.utils.logging import get_verbose_logger


def get_logger(name_path: str):
    rep = name_path.split(".")
    if rep[0] == "rcp_task_acquisition":
        rep[0] = "rcp"
    else:
        rep = ["rcp"] + rep
    return get_verbose_logger(".".join(rep))
