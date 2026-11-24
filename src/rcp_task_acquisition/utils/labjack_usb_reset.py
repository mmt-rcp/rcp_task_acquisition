import argparse
import platform
import subprocess
import sys
import time


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


def execute_usb_reset(usb_id: str):
    print(f"resetting {usb_id}")
    if platform.system() == "Windows":
        cmd = [
            # "runas",
            # "/noprofile",
            # "/user:Administrator",
            "pnputil.exe",
            "/restart-device",
            usb_id,
        ]
        prog = subprocess.Popen(cmd, stdin=subprocess.PIPE)
        # prog.stdin.write('password')
        out, err = prog.communicate()
        print(f"{prog.returncode=}")
        print(f"{out=}, {err=}")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--reset", action="store_true")
    parser.add_argument("usb_id", nargs="*", default=[])
    args = parser.parse_args()
    # print(args)
    if not args.usb_id:
        args.usb_id = find_labjack_usb_id()
    for usb_id in args.usb_id:
        print(usb_id)
        if args.reset:
            execute_usb_reset(usb_id)
    time.sleep(1)
    # input("Press ENTER to continue...")


if __name__ == "__main__":
    main()
