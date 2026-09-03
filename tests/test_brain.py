import json
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock, patch

from core.brain import JarvisBrain


def _make_brain(tmp_dir):
    with patch("core.brain.FACTS_FILE", Path(tmp_dir) / "facts.json"):
        return JarvisBrain(scanner=None, app_finder=None, auto_warmup=False)


class ValidateTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.brain = _make_brain(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_valid_decision_passes_through(self):
        decision = self.brain._validate(
            {"action": "open_app", "target": "chrome", "query": "", "amount": 0, "reply": "ok"}
        )
        self.assertEqual(decision["action"], "open_app")
        self.assertEqual(decision["target"], "chrome")

    def test_unknown_action_falls_back_to_none(self):
        decision = self.brain._validate({"action": "delete_system32", "target": "", "query": "", "amount": 0, "reply": ""})
        self.assertEqual(decision["action"], "none")

    def test_non_dict_input_falls_back_gracefully(self):
        decision = self.brain._validate("not a dict")
        self.assertEqual(decision["action"], "none")
        self.assertEqual(decision["target"], "")

    def test_amount_is_clamped(self):
        decision = self.brain._validate({"action": "set_timer", "target": "", "query": "", "amount": 99999, "reply": ""})
        self.assertEqual(decision["amount"], 500)

        decision = self.brain._validate({"action": "set_timer", "target": "", "query": "", "amount": -5, "reply": ""})
        self.assertEqual(decision["amount"], 0)

    def test_invalid_amount_type_defaults_to_zero(self):
        decision = self.brain._validate({"action": "set_timer", "target": "", "query": "", "amount": "muitos", "reply": ""})
        self.assertEqual(decision["amount"], 0)

    def test_reply_is_truncated(self):
        decision = self.brain._validate({"action": "chat", "target": "", "query": "", "amount": 0, "reply": "x" * 10000})
        self.assertLessEqual(len(decision["reply"]), 700)

    def test_all_declared_actions_are_valid(self):
        for action in JarvisBrain.ACTIONS:
            decision = self.brain._validate({"action": action, "target": "", "query": "", "amount": 0, "reply": ""})
            self.assertEqual(decision["action"], action)


class ParseDecisionTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.brain = _make_brain(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_parses_clean_json(self):
        content = json.dumps({"action": "chat", "target": "", "query": "", "amount": 0, "reply": "oi"})
        decision = self.brain._parse_decision(content)
        self.assertEqual(decision["action"], "chat")

    def test_repairs_json_wrapped_in_prose(self):
        payload = {"action": "chat", "target": "", "query": "", "amount": 0, "reply": "oi"}
        content = f"Aqui está a resposta:\n{json.dumps(payload)}\nFim."
        decision = self.brain._parse_decision(content)
        self.assertEqual(decision["action"], "chat")

    def test_unparsable_content_returns_empty_dict(self):
        decision = self.brain._parse_decision("isso não é json de jeito nenhum")
        self.assertEqual(decision, {})


class UnderstandTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.brain = _make_brain(self._tmp.name)

    def tearDown(self):
        self._tmp.cleanup()

    def test_understand_empty_text_short_circuits(self):
        decision = self.brain.understand("")
        self.assertEqual(decision["action"], "none")

    def test_understand_success_path(self):
        fake_response = MagicMock()
        fake_response.raise_for_status = MagicMock()
        fake_response.json.return_value = {
            "message": {
                "content": json.dumps(
                    {"action": "open_app", "target": "spotify", "query": "", "amount": 0, "reply": ""}
                )
            }
        }

        with patch.object(self.brain.session, "post", return_value=fake_response):
            decision = self.brain.understand("abre o spotify")

        self.assertEqual(decision["action"], "open_app")
        self.assertEqual(decision["target"], "spotify")
        self.assertTrue(self.brain.available)

    def test_understand_network_failure_falls_back_to_chat(self):
        with patch.object(self.brain.session, "post", side_effect=ConnectionError("no ollama")):
            decision = self.brain.understand("oi jarvis")

        self.assertEqual(decision["action"], "chat")
        self.assertTrue(decision["reply"])
        self.assertFalse(self.brain.available)

    def test_understand_retries_before_succeeding(self):
        fake_response = MagicMock()
        fake_response.raise_for_status = MagicMock()
        fake_response.json.return_value = {
            "message": {
                "content": json.dumps(
                    {"action": "chat", "target": "", "query": "", "amount": 0, "reply": "oi"}
                )
            }
        }

        with patch.object(
            self.brain.session,
            "post",
            side_effect=[ConnectionError("boom"), fake_response],
        ), patch("core.brain.time.sleep"):
            decision = self.brain.understand("oi")

        self.assertEqual(decision["action"], "chat")

    def test_remember_and_clear_memory(self):
        self.brain.remember("oi", "olá")
        self.assertEqual(len(self.brain.memory.get_messages()), 2)

        self.brain.clear_memory()
        self.assertEqual(self.brain.memory.get_messages(), [])

    def test_long_term_facts_appear_in_system_prompt(self):
        self.brain.long_term.remember("nome", "Gustavo")
        prompt = self.brain._system_prompt()
        self.assertIn("Gustavo", prompt)

    def test_describe_capabilities_is_nonempty(self):
        self.assertTrue(self.brain.describe_capabilities())


if __name__ == "__main__":
    unittest.main()
