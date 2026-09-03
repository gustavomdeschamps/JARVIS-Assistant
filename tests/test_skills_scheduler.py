import datetime
import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.skills.scheduler import SchedulerSkill


class SchedulerSkillTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.skill = SchedulerSkill(
            Path(self._tmp.name) / "schedule.json",
            poll_seconds=0.05,
            max_active_items=3,
        )

    def tearDown(self):
        self.skill.stop()
        self._tmp.cleanup()

    def test_create_timer(self):
        item, over_limit = self.skill.create_timer(10, label="café")
        self.assertFalse(over_limit)
        self.assertEqual(item["kind"], "timer")
        self.assertEqual(item["label"], "café")

    def test_create_reminder(self):
        item, over_limit = self.skill.create_reminder(5, "ligar pro dentista")
        self.assertEqual(item["kind"], "reminder")
        self.assertEqual(item["label"], "ligar pro dentista")

    def test_list_active_filters_by_kind(self):
        self.skill.create_timer(10)
        self.skill.create_reminder(10, "algo")

        self.assertEqual(len(self.skill.list_active(kind="timer")), 1)
        self.assertEqual(len(self.skill.list_active(kind="reminder")), 1)
        self.assertEqual(len(self.skill.list_active()), 2)

    def test_over_limit_rejected(self):
        for _ in range(3):
            self.skill.create_timer(10)

        item, over_limit = self.skill.create_timer(10)
        self.assertTrue(over_limit)
        self.assertIsNone(item)

    def test_cancel_by_id(self):
        item, _ = self.skill.create_timer(10)
        self.assertTrue(self.skill.cancel(item["id"]))
        self.assertEqual(self.skill.list_active(), [])

    def test_cancel_missing_returns_false(self):
        self.assertFalse(self.skill.cancel(999))

    def test_cancel_all_by_kind(self):
        self.skill.create_timer(10)
        self.skill.create_timer(10)
        self.skill.create_reminder(10, "x")

        removed = self.skill.cancel_all(kind="timer")
        self.assertEqual(removed, 2)
        self.assertEqual(len(self.skill.list_active(kind="reminder")), 1)

    def test_pop_due_marks_items_fired(self):
        item, _ = self.skill.create_timer(0)  # due immediately
        due = self.skill.pop_due(now=datetime.datetime.now() + datetime.timedelta(seconds=1))

        self.assertEqual(len(due), 1)
        self.assertEqual(due[0]["id"], item["id"])
        # Fired items no longer show up as active.
        self.assertEqual(self.skill.list_active(), [])
        # And popping again returns nothing.
        self.assertEqual(self.skill.pop_due(), [])

    def test_remaining_minutes_never_negative(self):
        item, _ = self.skill.create_timer(0)
        time.sleep(0.05)
        self.assertGreaterEqual(self.skill.remaining_minutes(item), 0.0)

    def test_background_poller_invokes_callback(self):
        fired = []
        self.skill.start(lambda item: fired.append(item))

        self.skill.create_timer(0)

        deadline = time.monotonic() + 2.0
        while not fired and time.monotonic() < deadline:
            time.sleep(0.02)

        self.assertEqual(len(fired), 1)

    def test_persists_across_instances(self):
        self.skill.create_timer(10, label="persistente")

        reloaded = SchedulerSkill(self.skill.store.path, poll_seconds=0.05)
        self.assertEqual(len(reloaded.list_active(kind="timer")), 1)


if __name__ == "__main__":
    unittest.main()
