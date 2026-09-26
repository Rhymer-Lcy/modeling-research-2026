"""Process-wide Q3 local-input guard built on Python audit hooks.

The allowlist in :mod:`src.alloc.receipts` is advisory unless every file access
in a Q3 process is forced through it.  Once :func:`install_q3_input_guard` has
run, the interpreter itself raises before any of the following can happen,
whichever library attempts it:

- opening any ``*.pdf`` path, and in particular either quarantined PDF, for
  any purpose including integrity hashing;
- opening a file under ``data_local/`` or ``docs_local/`` that is not in the
  explicit Q3 allowlist (B8, other attachments, the audit tree);
- opening an allowlisted input (local or tracked) with write intent;
- listing, scanning or globbing a directory under ``data_local/`` or
  ``docs_local/`` (no automatic source traversal);
- removing, renaming, truncating or re-permissioning anything there.

The audit event fires before the operating-system call, so a rejected file is
never opened, stated through the open, or read.  Every allowlisted read, local
or tracked, is recorded and, when ``T010_Q3_INPUT_LOG`` names a file, written there at exit so
the reproduction entry point can report exactly which inputs each generator
opened.  An installed hook cannot be removed; tests exercise it in a
subprocess.
"""

from __future__ import annotations

import atexit
import json
import os
import sys
from typing import Any

from src.paths import DATA_LOCAL, DOCS_LOCAL

from .receipts import (
    AUTHORIZED_Q3_INPUTS,
    ForbiddenQ3Input,
    UnauthorizedQ3Input,
    is_forbidden_path,
)

LOG_ENVIRONMENT_VARIABLE = "T010_Q3_INPUT_LOG"

_TRAVERSAL_EVENTS = frozenset({"os.listdir", "os.scandir", "glob.glob", "glob.glob/2"})
_MUTATION_EVENTS = frozenset({
    "os.remove", "os.rename", "os.rmdir", "os.mkdir", "os.chmod", "os.utime",
    "os.truncate", "os.link", "os.symlink", "shutil.rmtree", "shutil.move",
    "shutil.copyfile", "shutil.copymode", "shutil.copystat",
})
_WRITE_FLAGS = os.O_WRONLY | os.O_RDWR | os.O_CREAT | os.O_TRUNC | os.O_APPEND


def _normalize(path: str) -> str:
    return os.path.normcase(os.path.abspath(path))


_LOCAL_ROOTS = tuple(_normalize(os.fspath(root)) for root in (DATA_LOCAL, DOCS_LOCAL))
_ALLOWED = {_normalize(os.fspath(entry.path)): entry.key for entry in AUTHORIZED_Q3_INPUTS}

_STATE: dict[str, Any] = {"installed": False, "reads": set(), "denied": []}


def _as_text(path: object) -> str | None:
    if path is None or isinstance(path, int):
        return None
    try:
        return os.fsdecode(path)  # accepts str, bytes and path-like objects
    except TypeError:
        return None


def _under_local_root(normalized: str) -> bool:
    return any(normalized == root or normalized.startswith(root + os.sep) for root in _LOCAL_ROOTS)


def _write_intent(mode: object, flags: object) -> bool:
    if isinstance(mode, str):
        return any(character in mode for character in "wax+")
    if isinstance(flags, int):
        return bool(flags & _WRITE_FLAGS)
    return False


def _deny(error: type[ValueError], message: str) -> None:
    _STATE["denied"].append(message)
    raise error(message)


def _check_open(path: object, mode: object, flags: object) -> None:
    text = _as_text(path)
    if text is None:
        return
    if is_forbidden_path(text):
        _deny(ForbiddenQ3Input, "Q3 input guard: PDF open rejected before access: " + os.path.basename(text))
    normalized = _normalize(text)
    key = _ALLOWED.get(normalized)
    if key is None and not _under_local_root(normalized):
        return
    if _write_intent(mode, flags):
        _deny(ForbiddenQ3Input, "Q3 input guard: write intent on a Q3 input rejected: " + os.path.basename(text))
    if key is None:
        _deny(UnauthorizedQ3Input, "Q3 input guard: local input outside the Q3 allowlist rejected: " + os.path.basename(text))
    _STATE["reads"].add(key)


def _check_paths(event: str, args: tuple[Any, ...], error: type[ValueError], action: str) -> None:
    for argument in args:
        text = _as_text(argument)
        if text is None:
            continue
        if is_forbidden_path(text) or _under_local_root(_normalize(text)):
            _deny(error, "Q3 input guard: " + action + " rejected (" + event + "): " + os.path.basename(text))


def _hook(event: str, args: tuple[Any, ...]) -> None:
    if event == "open":
        _check_open(*(tuple(args) + (None, None, None))[:3])
    elif event in _TRAVERSAL_EVENTS:
        _check_paths(event, tuple(args[:1]), ForbiddenQ3Input, "automatic source traversal")
    elif event in _MUTATION_EVENTS:
        _check_paths(event, tuple(args), ForbiddenQ3Input, "local-input mutation")


def _write_log() -> None:
    target = os.environ.get(LOG_ENVIRONMENT_VARIABLE)
    if not target:
        return
    record = {"reads": sorted(_STATE["reads"]), "denied": list(_STATE["denied"])}
    with open(target, "w", encoding="utf-8", newline="\n") as handle:
        json.dump(record, handle, sort_keys=True)
        handle.write("\n")


def install_q3_input_guard() -> None:
    """Install the irreversible process-wide Q3 input guard (idempotent)."""
    if _STATE["installed"]:
        return
    sys.addaudithook(_hook)
    atexit.register(_write_log)
    _STATE["installed"] = True


def guard_installed() -> bool:
    """Return whether this process is running under the Q3 input guard."""
    return bool(_STATE["installed"])


def guard_record() -> dict[str, list[str]]:
    """Return the allowlist keys read so far and every denial raised."""
    return {"reads": sorted(_STATE["reads"]), "denied": list(_STATE["denied"])}


__all__ = [
    "LOG_ENVIRONMENT_VARIABLE",
    "guard_installed",
    "guard_record",
    "install_q3_input_guard",
]
