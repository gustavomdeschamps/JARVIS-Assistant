import unittest
from pathlib import Path
from tempfile import TemporaryDirectory

from core.memory import ConversationMemory, LongTermMemory


class ConversationMemoryTests(unittest.TestCase):
    def test_add_and_get_messages(self):
        memory = ConversationMemory(max_messages=4)
        memory.add_user("oi")
        memory.add_assistant("olá")

        self.assertEqual(
            memory.get_messages(),
            [
                {"role": "user", "content": "oi"},
                {"role": "assistant", "content": "olá"},
            ],
        )

    def test_empty_text_is_ignored(self):
        memory = ConversationMemory(max_messages=4)
        memory.add_user("")
        memory.add_assistant(None)
        self.assertEqual(memory.get_messages(), [])

    def test_clear_resets_messages_and_summary(self):
        memory = ConversationMemory(max_messages=2, summary_trigger=2)
        for i in range(6):
            memory.add_user(f"mensagem {i}")

        self.assertTrue(memory.get_summary())
        memory.clear()

        self.assertEqual(memory.get_messages(), [])
        self.assertEqual(memory.get_summary(), "")

    def test_window_bounded_and_old_messages_folded_into_summary(self):
        memory = ConversationMemory(max_messages=3, summary_trigger=4)

        for i in range(10):
            memory.add_user(f"pergunta {i}")

        messages = memory.get_messages()

        # The window is bounded (compaction batches, so it can sit
        # anywhere between max_messages and summary_trigger, never above).
        self.assertLessEqual(len(messages), 4)
        self.assertNotIn("pergunta 0", [m["content"] for m in messages])

        # The most recent message must still be present verbatim.
        self.assertEqual(messages[-1]["content"], "pergunta 9")

        # Older messages were folded into a running summary instead of
        # being silently lost.
        summary = memory.get_summary()
        self.assertIn("pergunta 0", summary)

    def test_summary_stays_bounded_in_length(self):
        memory = ConversationMemory(max_messages=2, summary_trigger=2)

        for i in range(200):
            memory.add_user("x" * 50 + str(i))

        self.assertLess(len(memory.get_summary()), 900)


class LongTermMemoryTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.path = Path(self._tmp.name) / "facts.json"

    def tearDown(self):
        self._tmp.cleanup()

    def test_remember_and_recall(self):
        memory = LongTermMemory(self.path)
        self.assertTrue(memory.remember("nome", "Gustavo"))
        self.assertEqual(memory.recall("nome"), "Gustavo")

    def test_recall_missing_key_returns_none(self):
        memory = LongTermMemory(self.path)
        self.assertIsNone(memory.recall("inexistente"))

    def test_remember_rejects_empty_key_or_value(self):
        memory = LongTermMemory(self.path)
        self.assertFalse(memory.remember("", "valor"))
        self.assertFalse(memory.remember("chave", ""))

    def test_forget_removes_key(self):
        memory = LongTermMemory(self.path)
        memory.remember("cor_favorita", "azul")

        self.assertTrue(memory.forget("cor_favorita"))
        self.assertIsNone(memory.recall("cor_favorita"))
        self.assertFalse(memory.forget("cor_favorita"))

    def test_forget_all_clears_everything(self):
        memory = LongTermMemory(self.path)
        memory.remember("a", "1")
        memory.remember("b", "2")

        memory.forget_all()

        self.assertEqual(memory.recall_all(), {})

    def test_max_facts_evicts_oldest(self):
        memory = LongTermMemory(self.path, max_facts=3)

        memory.remember("a", "1")
        memory.remember("b", "2")
        memory.remember("c", "3")
        memory.remember("d", "4")

        facts = memory.recall_all()
        self.assertEqual(len(facts), 3)
        self.assertNotIn("a", facts)
        self.assertIn("d", facts)

    def test_as_context_string_formats_facts(self):
        memory = LongTermMemory(self.path)
        memory.remember("nome", "Gustavo")

        self.assertIn("nome: Gustavo", memory.as_context_string())

    def test_persists_across_instances(self):
        LongTermMemory(self.path).remember("nome", "Gustavo")
        reloaded = LongTermMemory(self.path)
        self.assertEqual(reloaded.recall("nome"), "Gustavo")


if __name__ == "__main__":
    unittest.main()
