from __future__ import annotations

import os
import shlex
import subprocess
import time
from dataclasses import asdict, dataclass, field
from pathlib import Path
from typing import Mapping


@dataclass(slots=True)
class CommandResult:
    command: str
    cwd: str
    returncode: int
    stdout: str
    stderr: str
    runtime_seconds: float
    timed_out: bool = False
    metadata: dict[str, str] = field(default_factory=dict)

    @property
    def succeeded(self) -> bool:
        return self.returncode == 0 and not self.timed_out

    def to_dict(self) -> dict[str, object]:
        return asdict(self)


def run_command(
    command: str | list[str],
    cwd: str | Path,
    *,
    timeout: int | None = 300,
    env: Mapping[str, str] | None = None,
) -> CommandResult:
    if isinstance(command, str):
        args = command
        shell = True
        printable_command = command
    else:
        args = command
        shell = False
        printable_command = " ".join(shlex.quote(part) for part in command)

    merged_env = os.environ.copy()
    if env:
        merged_env.update(env)

    started = time.perf_counter()
    try:
        completed = subprocess.run(
            args,
            cwd=str(cwd),
            env=merged_env,
            shell=shell,
            capture_output=True,
            text=True,
            timeout=timeout,
            check=False,
        )
        return CommandResult(
            command=printable_command,
            cwd=str(cwd),
            returncode=completed.returncode,
            stdout=completed.stdout,
            stderr=completed.stderr,
            runtime_seconds=time.perf_counter() - started,
        )
    except subprocess.TimeoutExpired as exc:
        return CommandResult(
            command=printable_command,
            cwd=str(cwd),
            returncode=124,
            stdout=exc.stdout or "",
            stderr=(exc.stderr or "") + f"\nCommand timed out after {timeout} seconds.",
            runtime_seconds=time.perf_counter() - started,
            timed_out=True,
        )
