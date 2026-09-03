import unittest
from pathlib import Path
from tempfile import TemporaryDirectory
from unittest.mock import MagicMock

from core.skills.weather import WeatherSkill


def _fake_response(payload, ok=True):
    response = MagicMock()
    response.json.return_value = payload
    response.raise_for_status = MagicMock()
    if not ok:
        response.raise_for_status.side_effect = Exception("boom")
    return response


_SAMPLE_PAYLOAD = {
    "current_condition": [
        {
            "temp_C": "24",
            "FeelsLikeC": "26",
            "humidity": "55",
            "weatherDesc": [{"value": "Sunny"}],
            "lang_pt": [{"value": "Ensolarado"}],
        }
    ]
}


class WeatherSkillTests(unittest.TestCase):
    def setUp(self):
        self._tmp = TemporaryDirectory()
        self.cache_path = Path(self._tmp.name) / "weather.json"

    def tearDown(self):
        self._tmp.cleanup()

    def _make_skill(self, session):
        return WeatherSkill(self.cache_path, cache_minutes=20, session=session)

    def test_successful_lookup_is_formatted_in_portuguese(self):
        session = MagicMock()
        session.get.return_value = _fake_response(_SAMPLE_PAYLOAD)

        skill = self._make_skill(session)
        ok, text = skill.get("São Paulo")

        self.assertTrue(ok)
        self.assertIn("24", text)
        self.assertIn("ensolarado", text.lower())
        self.assertIn("São Paulo", text)

    def test_network_failure_returns_friendly_message(self):
        session = MagicMock()
        session.get.side_effect = Exception("network down")

        skill = self._make_skill(session)
        ok, text = skill.get("Curitiba")

        self.assertFalse(ok)
        self.assertIsInstance(text, str)
        self.assertTrue(text)

    def test_second_call_within_ttl_uses_cache_not_network(self):
        session = MagicMock()
        session.get.return_value = _fake_response(_SAMPLE_PAYLOAD)

        skill = self._make_skill(session)
        skill.get("Recife")
        skill.get("Recife")

        self.assertEqual(session.get.call_count, 1)

    def test_different_cities_are_cached_separately(self):
        session = MagicMock()
        session.get.return_value = _fake_response(_SAMPLE_PAYLOAD)

        skill = self._make_skill(session)
        skill.get("Recife")
        skill.get("Salvador")

        self.assertEqual(session.get.call_count, 2)

    def test_malformed_payload_handled_gracefully(self):
        session = MagicMock()
        session.get.return_value = _fake_response({"unexpected": True})

        skill = self._make_skill(session)
        ok, text = skill.get("Manaus")

        self.assertTrue(ok)
        self.assertIsInstance(text, str)


if __name__ == "__main__":
    unittest.main()
