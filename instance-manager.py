import argparse
import os
import pickle
import pwd
import shutil
import subprocess
from collections.abc import Callable
from typing import TypeVar, TypedDict
import filecmp
from getpass import getpass

DATADIR_ROOT = "/var/lib/edgedb/5/"
UNITFILE = "edgedb-server-5@.service"
SYSTEM_UNITFILE = os.path.join("/etc/systemd/system/", UNITFILE)

# User state
GID = os.getegid()
UID = os.geteuid()
EDGEDB_USER = pwd.getpwnam("edgedb")
EDGEDB_GID = EDGEDB_USER.pw_gid
EDGEDB_UID = EDGEDB_USER.pw_uid


def get_args():
    parser = argparse.ArgumentParser(
        prog="EdgeDB Instance Manager",
        description="Manage multiple bare-metal instances of EdgeDB",
    )

    subcommands = parser.add_subparsers()

    create_parser = subcommands.add_parser(
        name="Create",
        help="Create a new instance",
        epilog="Some arguments will be loaded from disk if not provided",
    )
    create_parser.set_defaults(mode="create")
    create_parser.add_argument("-n", "--name")
    create_parser.add_argument("-p", "--port", type=int)

    delete_parser = subcommands.add_parser(name="Delete")
    delete_parser.set_defaults(mode="delete")
    delete_parser.add_argument("name", required=True)

    redeploy_parser = subcommands.add_parser(
        name="Redeploy", help="Redeploy an instance"
    )
    redeploy_parser.set_defaults(mode="redeploy")
    redeploy_parser.add_argument("name", required=True)
    redeploy_parser.add_argument("--change-password", action="store_true")

    args = parser.parse_args()

    return args


def run_as_edgedb(fn: Callable):
    os.setegid(EDGEDB_GID)
    os.seteuid(EDGEDB_UID)
    fn()
    os.setegid(GID)
    os.seteuid(UID)


def fatal(*msg):
    """
    Returns an exception to raise
    """
    return SystemExit(" ".join(["[FATAL]", *msg]))


def warn(*msg):
    print("[WARN]", *msg)


def info(*msg):
    print(*msg)


def done():
    info("  Done!")


def prompt_bool(prompt: str, default=False):
    output = None

    while True:
        value = input(prompt + " [Y/n]" if default else " [y/N]")
        if value == "y" or value == "Y":
            output = True
            break
        elif value == "n" or value == "N":
            output = False
            break

    return output


DataType = TypeVar("DataType")


def prompt_required(
    prompt: str, hidden=False, dtype: Callable[[str], DataType] = str
) -> DataType:
    output = None

    while True:
        output = getpass(prompt) if hidden else input(prompt)
        if output != "":
            try:
                return dtype(output)
            except Exception:
                pass


def check_unit_file():
    if not os.path.exists(SYSTEM_UNITFILE):
        info("System does not have the unitfile installed! Copying...")
        shutil.copy(UNITFILE, SYSTEM_UNITFILE)
        done()

    if not filecmp.cmp(UNITFILE, SYSTEM_UNITFILE):
        warn("Unitfile differs from version installed on system!")
        reinstall = prompt_bool("Install current unitfile?")
        if reinstall:
            shutil.copy(UNITFILE, SYSTEM_UNITFILE)
            done()


class InstanceState(TypedDict):
    """Data saved between runs"""

    port: int


class Instance(TypedDict):
    """Data for an instance"""

    name: str
    port: int
    password: str


def _get_instance_file(name: str):
    os.makedirs(".instances", exist_ok=True)
    return ".instances/" + name


def _load_instance_store(name: str) -> InstanceState:
    with open(_get_instance_file(name), "rb") as f:
        return pickle.load(f)


def _save_instance_store(name: str, data: InstanceState):
    with open(_get_instance_file(name), "wb") as f:
        return pickle.dump(data, f)


def _get_instance_runstate_dir(name: str):
    # Weird command to get envvar from systemd
    proc = subprocess.run(
        f"""systemctl show {UNITFILE}{name}.service -P Environment | grep -o -m 1 -- "EDGEDB_SERVER_RUNSTATE_DIR=[^ ]\\+" | awk -F "=" '{{print $2}}'""",
        stdout=subprocess.PIPE,
        text=True,
    )
    # Make sure we actually got something
    if proc.returncode != 0 or len(proc.stdout.strip()) == 0:
        raise fatal("Failed to get the instances RUNSTATE_DIR")
    return proc.stdout


def create_instance_dirs(name: str):
    os.makedirs(os.path.join(DATADIR_ROOT, name), exist_ok=True)
    os.makedirs(_get_instance_runstate_dir(name), exist_ok=True)


def prompt_instance_data(
    name: str | None, port: int | None, *, password: str | None = None
):
    new_name = name or prompt_required("Enter the name of the instance")
    new_port = port or prompt_required("Enter the port of the instance", dtype=int)
    new_password = password or prompt_required(
        "Enter the default password of the instance", hidden=True
    )

    return Instance(name=new_name, port=new_port, password=new_password)


def main():
    if UID != 0:
        raise fatal("This script must be run as root!")

    args = get_args()

    check_unit_file()

    match args.mode:
        case "create":
            create(name=args.name, port=args.port)
        case "delete":
            delete(name=args.name)
        case "redeploy":
            redeploy(name=args.name, change_password=args.change_password)


def create(name: str | None, port: int | None):
    instance = prompt_instance_data(name, port)
    pass


def delete(name: str):
    pass


def redeploy(name: str, change_password: bool):
    pass


if __name__ == "__main__":
    main()
