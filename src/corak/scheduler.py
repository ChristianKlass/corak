"""Automatic rotation, run by systemd rather than by this process.

A resident GUI process would have to stay running, be autostarted, and survive
crashes to keep a schedule. A systemd user timer costs nothing while idle, comes
back after a logout, and reruns the same headless command the app itself calls.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path

SERVICE = "corak.service"
TIMER = "corak.timer"


class SchedulerError(RuntimeError):
    pass


def unit_dir() -> Path:
    base = os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config"
    return Path(base) / "systemd" / "user"


def executable() -> str:
    """The corak command to run, preferring the one this process came from."""
    candidate = Path(sys.prefix) / "bin" / "corak"
    if candidate.exists():
        return str(candidate)
    found = shutil.which("corak")
    if found:
        return found
    return f"{sys.executable} -m corak"


def systemctl(*args: str) -> str:
    if shutil.which("systemctl") is None:
        raise SchedulerError("systemctl is not available")
    try:
        done = subprocess.run(
            ["systemctl", "--user", *args], capture_output=True, text=True, timeout=20, check=False
        )
    except (OSError, subprocess.SubprocessError) as exc:
        raise SchedulerError(str(exc)) from exc
    if done.returncode != 0 and "is-enabled" not in args and "is-active" not in args:
        raise SchedulerError(done.stderr.strip() or f"systemctl {' '.join(args)} failed")
    return done.stdout.strip()


def service_text() -> str:
    return (
        "[Unit]\n"
        "Description=Generate and set a corak wallpaper\n"
        "After=graphical-session.target\n"
        "PartOf=graphical-session.target\n"
        # A rotation that fires before the compositor is ready, or during an
        # upgrade that briefly takes the executable away, was simply dropped.
        # The limit is what stops a broken install retrying into the journal
        # for as long as the session lasts.
        "StartLimitIntervalSec=300\n"
        "StartLimitBurst=3\n"
        "\n"
        "[Service]\n"
        "Type=oneshot\n"
        f"ExecStart={executable()} --next\n"
        # Three tries, half a minute apart. An upgrade is away for under a
        # minute, so the second or third lands after the binary is back.
        "Restart=on-failure\n"
        "RestartSec=30\n"
    )


def timer_text(interval_minutes: int) -> str:
    return (
        "[Unit]\n"
        "Description=Rotate the corak wallpaper\n"
        "\n"
        "[Timer]\n"
        # Not persistent: catching up on rotations missed while logged out would
        # fire a burst of them at login for no benefit.
        "OnStartupSec=2min\n"
        f"OnUnitActiveSec={int(interval_minutes)}min\n"
        "Persistent=false\n"
        "\n"
        "[Install]\n"
        "WantedBy=timers.target\n"
    )


def install(interval_minutes: int) -> None:
    directory = unit_dir()
    directory.mkdir(parents=True, exist_ok=True)
    (directory / SERVICE).write_text(service_text())
    (directory / TIMER).write_text(timer_text(interval_minutes))
    systemctl("daemon-reload")


def enable(interval_minutes: int) -> None:
    install(interval_minutes)
    systemctl("enable", "--now", TIMER)


def disable() -> None:
    systemctl("disable", "--now", TIMER)


def enabled() -> bool:
    return systemctl("is-enabled", TIMER) == "enabled"


def next_run() -> str:
    """A human-readable time of the next rotation, empty if not scheduled."""
    try:
        for line in systemctl("list-timers", TIMER, "--no-legend", "--no-pager").splitlines():
            if TIMER in line:
                return line.strip()
    except SchedulerError:
        pass
    return ""
