import platform
import subprocess


def _find_labjack_usb_id_windows():
    output = subprocess.check_output(
        [
            "pnputil.exe",
            "/enum-devices",
            "/class",
            "LabJackUSB",
        ]
    ).decode()
    front = "Instance ID:"
    values = [
        line.split(front, 1)[1].strip() for line in output.splitlines() if line.startswith(front)
    ]
    return values


def find_labjack_usb_id() -> list[str]:
    if platform.system() == "Windows":
        return _find_labjack_usb_id_windows()
    raise RuntimeError(f"find_labjack_usb_id not implemented here")  # TODO


def main():
    for usb_id in find_labjack_usb_id():
        print(usb_id)


if __name__ == "__main__":
    main()
