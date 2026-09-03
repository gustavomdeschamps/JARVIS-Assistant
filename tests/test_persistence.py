import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.persistence import JsonStore


class JsonStoreTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "nested" / "store.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_load_missing_file_returns_default(self):
        store = JsonStore(self.path, default={"items": []})
        self.assertEqual(store.load(), {"items": []})

    def test_default_is_not_shared_between_loads(self):
        store = JsonStore(self.path, default={"items": []})
        data = store.load()
        data["items"].append(1)
        # A second load must not see the mutation above.
        self.assertEqual(store.load(), {"items": []})

    def test_save_then_load_roundtrip(self):
        store = JsonStore(self.path, default={})
        store.save({"a": 1, "b": [1, 2, 3]})
        self.assertEqual(store.load(), {"a": 1, "b": [1, 2, 3]})

    def test_save_creates_parent_directories(self):
        store = JsonStore(self.path, default={})
        store.save({"x": True})
        self.assertTrue(self.path.exists())

    def test_corrupted_file_falls_back_to_default(self):
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.path.write_text("{not valid json", encoding="utf-8")

        store = JsonStore(self.path, default={"ok": True})
        self.assertEqual(store.load(), {"ok": True})

    def test_mutate_is_atomic_read_modify_write(self):
        store = JsonStore(self.path, default={"count": 0})

        def increment(data):
            data["count"] += 1
            return data

        store.mutate(increment)
        store.mutate(increment)
        result = store.mutate(increment)

        self.assertEqual(result["count"], 3)
        self.assertEqual(store.load()["count"], 3)

    def test_no_leftover_tmp_file_after_save(self):
        store = JsonStore(self.path, default={})
        store.save({"a": 1})

        tmp_path = self.path.with_suffix(self.path.suffix + ".tmp")
        self.assertFalse(tmp_path.exists())


if __name__ == "__main__":
    unittest.main()
