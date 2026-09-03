import importlib
import os
import unittest


class ConfigDefaultsTests(unittest.TestCase):
    def test_data_dir_exists(self):
        import config

        self.assertTrue(config.DATA_DIR.exists())

    def test_destructive_targets_include_shutdown_and_restart(self):
        import config

        self.assertIn("shutdown", config.DESTRUCTIVE_TARGETS)
        self.assertIn("restart", config.DESTRUCTIVE_TARGETS)
        self.assertNotIn("lock", config.DESTRUCTIVE_TARGETS)
        self.assertNotIn("sleep", config.DESTRUCTIVE_TARGETS)

    def test_ollama_url_built_from_host_and_port(self):
        import config

        self.assertIn(config.OLLAMA_HOST, config.OLLAMA_URL)
        self.assertIn(str(config.OLLAMA_PORT), config.OLLAMA_URL)


class ConfigEnvOverrideTests(unittest.TestCase):
    """`config.py` reads JARVIS_* env vars at import time, so we reload the
    module under a patched environment to verify overrides actually apply.
    """

    def setUp(self):
        import config

        self._config = config

    def tearDown(self):
        for key in list(os.environ):
            if key.startswith("JARVIS_"):
                del os.environ[key]
        importlib.reload(self._config)

    def test_primary_model_override(self):
        os.environ["JARVIS_PRIMARY_MODEL"] = "llama3.2:3b"
        reloaded = importlib.reload(self._config)
        self.assertEqual(reloaded.PRIMARY_MODEL, "llama3.2:3b")

    def test_int_override(self):
        os.environ["JARVIS_CONVERSATION_MEMORY_MESSAGES"] = "42"
        reloaded = importlib.reload(self._config)
        self.assertEqual(reloaded.CONVERSATION_MEMORY_MESSAGES, 42)

    def test_bool_override(self):
        os.environ["JARVIS_LOG_TO_FILE"] = "false"
        reloaded = importlib.reload(self._config)
        self.assertFalse(reloaded.LOG_TO_FILE)

    def test_invalid_int_falls_back_to_default(self):
        os.environ["JARVIS_ROUTER_MAX_TOKENS"] = "not-a-number"
        reloaded = importlib.reload(self._config)
        self.assertIsInstance(reloaded.ROUTER_MAX_TOKENS, int)


if __name__ == "__main__":
    unittest.main()
