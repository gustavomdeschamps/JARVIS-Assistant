"""Timers and reminders: "toque um timer de 10 minutos", "me lembre em
20 minutos de ligar para o dentista".

Both are the same mechanism — "say/do something after N minutes" — so
they share one persisted store and one background poller thread. The only
difference is cosmetic: a *timer* gets a generic "seu timer terminou"
message, a *reminder* carries the text the user asked to be reminded of.

The poller thread is intentionally simple (a plain ``while`` loop with a
short sleep) rather than using ``sched`` or per-item timers, because items
are added/cancelled from other threads at any time and this way there is
never a stale ``threading.Timer`` to track down and cancel.
"""

import datetime
import threading
import time

from core.persistence import JsonStore

_KIND_TIMER = "timer"
_KIND_REMINDER = "reminder"


class SchedulerSkill:
    def __init__(self, path, poll_seconds=1.0, max_active_items=50):
        self.store = JsonStore(path, default={"next_id": 1, "items": []})
        self.poll_seconds = float(poll_seconds)
        self.max_active_items = int(max_active_items)

        self._thread = None
        self._stop_event = threading.Event()

    # -----------------------------------------------------------
    # CREATE
    # -----------------------------------------------------------

    def _create(self, kind, minutes, label):
        minutes = max(0.0, float(minutes or 0))
        label = str(label or "").strip()
        now = datetime.datetime.now()
        due_at = now + datetime.timedelta(minutes=minutes)

        result = {"item": None, "over_limit": False}

        def _mutate(data):
            active = [item for item in data.get("items", []) if not item.get("fired")]
            if len(active) >= self.max_active_items:
                result["over_limit"] = True
                return data

            item_id = data.get("next_id", 1)
            item = {
                "id": item_id,
                "kind": kind,
                "label": label,
                "created_at": now.isoformat(timespec="seconds"),
                "due_at": due_at.isoformat(timespec="seconds"),
                "fired": False,
            }
            data.setdefault("items", []).append(item)
            data["next_id"] = item_id + 1
            result["item"] = item
            return data

        self.store.mutate(_mutate)
        return result["item"], result["over_limit"]

    def create_timer(self, minutes, label=""):
        return self._create(_KIND_TIMER, minutes, label)

    def create_reminder(self, minutes, label):
        return self._create(_KIND_REMINDER, minutes, label)

    # -----------------------------------------------------------
    # QUERY
    # -----------------------------------------------------------

    def list_active(self, kind=None):
        items = [
            item
            for item in self.store.load().get("items", [])
            if not item.get("fired")
        ]

        if kind:
            items = [item for item in items if item.get("kind") == kind]

        items.sort(key=lambda item: item.get("due_at", ""))
        return items

    def remaining_minutes(self, item):
        try:
            due_at = datetime.datetime.fromisoformat(item["due_at"])
        except (KeyError, ValueError):
            return 0.0

        delta = (due_at - datetime.datetime.now()).total_seconds() / 60.0
        return max(0.0, round(delta, 1))

    # -----------------------------------------------------------
    # CANCEL
    # -----------------------------------------------------------

    def cancel(self, item_id):
        item_id = int(item_id)
        found = {"value": False}

        def _mutate(data):
            items = data.get("items", [])
            new_items = [item for item in items if item.get("id") != item_id]
            found["value"] = len(new_items) != len(items)
            data["items"] = new_items
            return data

        self.store.mutate(_mutate)
        return found["value"]

    def cancel_all(self, kind=None):
        removed = {"count": 0}

        def _mutate(data):
            items = data.get("items", [])
            if kind:
                keep = [item for item in items if item.get("kind") != kind or item.get("fired")]
            else:
                keep = [item for item in items if item.get("fired")]
            removed["count"] = len(items) - len(keep)
            data["items"] = keep
            return data

        self.store.mutate(_mutate)
        return removed["count"]

    # -----------------------------------------------------------
    # DUE ITEMS (used by both the poller and by tests directly)
    # -----------------------------------------------------------

    def pop_due(self, now=None):
        now = now or datetime.datetime.now()
        due = []

        def _mutate(data):
            items = data.get("items", [])
            for item in items:
                if item.get("fired"):
                    continue
                try:
                    due_at = datetime.datetime.fromisoformat(item["due_at"])
                except (KeyError, ValueError):
                    continue
                if due_at <= now:
                    item["fired"] = True
                    due.append(dict(item))
            data["items"] = items
            return data

        self.store.mutate(_mutate)
        return due

    # -----------------------------------------------------------
    # BACKGROUND POLLER
    # -----------------------------------------------------------

    def start(self, callback):
        """Start the background poller; ``callback(item)`` fires per due item."""

        if self._thread and self._thread.is_alive():
            return

        self._stop_event.clear()

        def _loop():
            while not self._stop_event.is_set():
                try:
                    for item in self.pop_due():
                        try:
                            callback(item)
                        except Exception:
                            pass
                except Exception:
                    pass

                self._stop_event.wait(self.poll_seconds)

        self._thread = threading.Thread(target=_loop, daemon=True)
        self._thread.start()

    def stop(self):
        self._stop_event.set()
        if self._thread:
            self._thread.join(timeout=2)
