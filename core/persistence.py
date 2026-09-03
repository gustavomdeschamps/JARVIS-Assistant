"""Small, dependency-free JSON persistence helper.

Every "skill" that needs to remember something across restarts (notes,
timers, reminders, long-term facts, ...) goes through :class:`JsonStore`
instead of hand-rolling its own file I/O. It gives every one of them, for
free:

- Thread-safety (a single :class:`threading.RLock` per store instance).
- Atomic writes (write to a temp file, then ``os.replace`` it over the
  real file) so a crash or a power loss mid-write can never leave a
  half-written, corrupted JSON file behind.
- Defensive reads: a corrupted or missing file never raises into calling
  code, it just falls back to the caller-supplied default value.
"""

import copy
import json
import os
import threading
from pathlib import Path


class JsonStore:
    """A tiny, thread-safe, atomic JSON document store backed by a file."""

    def __init__(self, path, default=None):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)

        self._default = default if default is not None else {}
        self._lock = threading.RLock()

    # -----------------------------------------------------------
    # READ
    # -----------------------------------------------------------

    def load(self):
        with self._lock:
            try:
                with open(self.path, "r", encoding="utf-8") as handle:
                    return json.load(handle)
            except FileNotFoundError:
                return self._clone_default()
            except (json.JSONDecodeError, OSError, UnicodeDecodeError):
                # Corrupted file: never crash the assistant over it, just
                # start fresh from the default shape.
                return self._clone_default()

    # -----------------------------------------------------------
    # WRITE
    # -----------------------------------------------------------

    def save(self, data):
        with self._lock:
            tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")

            with open(tmp_path, "w", encoding="utf-8") as handle:
                json.dump(data, handle, ensure_ascii=False, indent=2)
                handle.flush()
                os.fsync(handle.fileno())

            os.replace(tmp_path, self.path)

    # -----------------------------------------------------------
    # MUTATE
    # -----------------------------------------------------------

    def mutate(self, function):
        """Load, run ``function(data) -> data``, save, return the result.

        Holds the lock across the whole read-modify-write cycle so callers
        get a real compare-and-swap instead of a race between threads.
        """

        with self._lock:
            data = self.load()
            data = function(data)
            self.save(data)
            return data

    def _clone_default(self):
        # A deep copy matters here: the default is typically a nested
        # structure like {"items": []}, and a shallow copy would leave
        # that inner list shared between every "missing file" load,
        # so mutating one caller's result would corrupt the next.
        return copy.deepcopy(self._default)
