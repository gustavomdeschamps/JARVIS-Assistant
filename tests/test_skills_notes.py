import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.skills.notes import NotesSkill


class NotesSkillTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.skill = NotesSkill(Path(self._tmp.name) / "notes.json")

    def tearDown(self):
        self._tmp.cleanup()

    def test_add_returns_note_with_id(self):
        note = self.skill.add("comprar leite")
        self.assertEqual(note["text"], "comprar leite")
        self.assertEqual(note["id"], 1)

    def test_add_empty_text_returns_none(self):
        self.assertIsNone(self.skill.add("   "))

    def test_list_returns_newest_first(self):
        self.skill.add("primeira")
        self.skill.add("segunda")
        self.skill.add("terceira")

        notes = self.skill.list()
        self.assertEqual([note["text"] for note in notes], ["terceira", "segunda", "primeira"])

    def test_list_respects_limit(self):
        for i in range(5):
            self.skill.add(f"nota {i}")

        self.assertEqual(len(self.skill.list(limit=2)), 2)

    def test_delete_existing(self):
        note = self.skill.add("apagar isso")
        self.assertTrue(self.skill.delete(note["id"]))
        self.assertEqual(self.skill.list(), [])

    def test_delete_missing_returns_false(self):
        self.assertFalse(self.skill.delete(999))

    def test_delete_last(self):
        self.skill.add("primeira")
        self.skill.add("segunda")

        deleted = self.skill.delete_last()
        self.assertEqual(deleted["text"], "segunda")
        self.assertEqual([note["text"] for note in self.skill.list()], ["primeira"])

    def test_delete_last_when_empty(self):
        self.assertIsNone(self.skill.delete_last())

    def test_clear(self):
        self.skill.add("a")
        self.skill.add("b")
        self.skill.clear()
        self.assertEqual(self.skill.count(), 0)

    def test_ids_increase_monotonically_even_after_deletes(self):
        first = self.skill.add("a")
        self.skill.delete(first["id"])
        second = self.skill.add("b")
        self.assertEqual(second["id"], 2)


if __name__ == "__main__":
    unittest.main()
