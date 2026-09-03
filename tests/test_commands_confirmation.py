"""Tests for the destructive-action confirmation state machine in
CommandSystem, without touching real hardware, Ollama, or the
project's real data directory: voice/scanner/app_finder/brain/windows
are all replaced with mocks, and the skills that do touch disk are
repointed at a temp directory right after construction.
"""

import time
import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

import config
from core.commands import CommandSystem
from core.skills import NotesSkill, SchedulerSkill, WeatherSkill


class _FakeBrain:
    def __init__(self, decision):
        self._decision = decision
        self.remembered = []
        self.long_term = MagicMock()

    def understand(self, text):
        return dict(self._decision)

    def remember(self, user_text, assistant_text):
        self.remembered.append((user_text, assistant_text))

    def clear_memory(self):
        pass


def _decision(action="chat", target="", query="", amount=0, reply=""):
    return {"action": action, "target": target, "query": query, "amount": amount, "reply": reply}


class CommandSystemConfirmationTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        tmp_path = Path(self._tmp.name)

        self.voice = MagicMock()
        self.brain = _FakeBrain(_decision(action="system_power", target="shutdown"))

        self.commands = CommandSystem(
            self.voice,
            scanner=MagicMock(),
            app_finder=MagicMock(),
            brain=self.brain,
        )

        # Repoint disk-backed skills at a temp dir so tests never touch
        # the real project data/ directory, and stop+restart the
        # scheduler pointed at the new location.
        self.commands.scheduler.stop()
        self.commands.notes = NotesSkill(tmp_path / "notes.json")
        self.commands.scheduler = SchedulerSkill(tmp_path / "schedule.json", poll_seconds=0.05)
        self.commands.scheduler.start(self.commands._on_schedule_due)
        self.commands.weather = WeatherSkill(tmp_path / "weather.json")

        # Keep the real WindowsController (its normalize()/POWER_ACTIONS
        # drive actual control-flow decisions in CommandSystem), but
        # replace the one method that would really touch the OS so tests
        # can never actually shut a machine down.
        self.commands.windows.power_action = MagicMock(return_value=True)

    def tearDown(self):
        self.commands.shutdown()
        self._tmp.cleanup()

    def test_shutdown_requires_confirmation_first(self):
        result = self.commands.execute("desliga o computador")

        self.assertIsNotNone(self.commands.pending_confirmation)
        self.commands.windows.power_action.assert_not_called()
        self.assertIn(config.CONFIRMATION_WORD, result["text"])

    def test_confirming_executes_the_action(self):
        self.commands.execute("desliga o computador")
        self.commands.windows.power_action.return_value = True

        result = self.commands.execute(config.CONFIRMATION_WORD)

        self.commands.windows.power_action.assert_called_once_with("shutdown")
        self.assertIsNone(self.commands.pending_confirmation)
        self.assertIn("Desligando", result["text"])

    def test_cancelling_does_not_execute(self):
        self.commands.execute("desliga o computador")

        result = self.commands.execute(config.CANCEL_WORD)

        self.commands.windows.power_action.assert_not_called()
        self.assertIsNone(self.commands.pending_confirmation)
        self.assertIn("cancel", result["text"].lower())

    def test_unrelated_reply_clears_pending_state_without_executing(self):
        self.commands.execute("desliga o computador")

        # A completely unrelated follow-up should not be interpreted as
        # a confirmation, and should not silently execute the action.
        self.commands.brain = _FakeBrain(_decision(action="chat", reply="oi!"))
        self.commands.execute("na verdade, que horas são?")

        self.commands.windows.power_action.assert_not_called()
        self.assertIsNone(self.commands.pending_confirmation)

    def test_confirmation_expires(self):
        self.commands.execute("desliga o computador")
        self.commands.pending_confirmation["expires_at"] = time.monotonic() - 1

        self.commands.brain = _FakeBrain(_decision(action="chat", reply="oi"))
        self.commands.execute(config.CONFIRMATION_WORD)

        self.commands.windows.power_action.assert_not_called()

    def test_lock_executes_immediately_without_confirmation(self):
        self.commands.brain = _FakeBrain(_decision(action="system_power", target="lock"))
        self.commands.windows.power_action.return_value = True

        result = self.commands.execute("trava a tela")

        self.commands.windows.power_action.assert_called_once_with("lock")
        self.assertIsNone(self.commands.pending_confirmation)
        self.assertIn("bloqueada", result["text"].lower())


class CommandSystemRoutingTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        tmp_path = Path(self._tmp.name)

        self.voice = MagicMock()
        self.brain = _FakeBrain(_decision())

        self.commands = CommandSystem(
            self.voice, scanner=MagicMock(), app_finder=MagicMock(), brain=self.brain
        )

        self.commands.scheduler.stop()
        self.commands.notes = NotesSkill(tmp_path / "notes.json")
        self.commands.scheduler = SchedulerSkill(tmp_path / "schedule.json", poll_seconds=0.05)
        self.commands.scheduler.start(self.commands._on_schedule_due)
        self.commands.windows = MagicMock()

    def tearDown(self):
        self.commands.shutdown()
        self._tmp.cleanup()

    def test_calculate_routes_to_skill(self):
        self.commands.brain = _FakeBrain(_decision(action="calculate", query="2 + 2"))
        result = self.commands.execute("quanto é 2 mais 2")
        self.assertIn("4", result["text"])

    def test_add_and_list_note(self):
        self.commands.brain = _FakeBrain(_decision(action="add_note", query="comprar leite"))
        self.commands.execute("anota aí")

        self.commands.brain = _FakeBrain(_decision(action="list_notes"))
        result = self.commands.execute("quais são minhas notas")
        self.assertIn("comprar leite", result["text"])

    def test_remember_and_recall_fact_uses_long_term_memory(self):
        long_term = MagicMock()
        long_term.remember.return_value = True
        long_term.recall.return_value = "Gustavo"

        self.commands.brain = _FakeBrain(_decision(action="remember_fact", target="nome", query="Gustavo"))
        self.commands.brain.long_term = long_term
        self.commands.execute("meu nome é Gustavo")
        long_term.remember.assert_called_once_with("nome", "Gustavo")

        self.commands.brain = _FakeBrain(_decision(action="recall_fact", target="nome"))
        self.commands.brain.long_term = long_term
        result = self.commands.execute("qual é o meu nome")
        self.assertIn("Gustavo", result["text"])

    def test_repeat_last_returns_previous_response(self):
        self.commands.brain = _FakeBrain(_decision(action="chat", reply="primeira resposta"))
        self.commands.execute("oi")

        self.commands.brain = _FakeBrain(_decision(action="repeat_last"))
        result = self.commands.execute("repete")
        self.assertEqual(result["text"], "primeira resposta")

    def test_unknown_action_falls_back_safely(self):
        self.commands.brain = _FakeBrain({"action": "algo_nao_mapeado", "target": "", "query": "", "amount": 0, "reply": ""})
        result = self.commands.execute("faça algo estranho")
        self.assertTrue(result["text"])


if __name__ == "__main__":
    unittest.main()
