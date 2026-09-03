import unittest
from unittest.mock import MagicMock, patch

from core.windows_controller import WindowsController


class NormalizeTests(unittest.TestCase):
    def setUp(self):
        self.controller = WindowsController(app_finder=MagicMock())

    def test_lowercases_and_strips_accents(self):
        self.assertEqual(self.controller.normalize("Configurações"), "configuracoes")

    def test_empty_input(self):
        self.assertEqual(self.controller.normalize(""), "")
        self.assertEqual(self.controller.normalize(None), "")

    def test_strips_whitespace(self):
        self.assertEqual(self.controller.normalize("  Área de Trabalho  "), "area de trabalho")


class CrossPlatformSafetyTests(unittest.TestCase):
    """On a non-Windows box, ctypes.windll does not exist. The controller
    must still construct and degrade gracefully instead of raising.
    """

    def test_constructs_without_windll(self):
        controller = WindowsController(app_finder=MagicMock())
        self.assertIsNone(controller.user32)

    def test_press_key_returns_false_without_windll(self):
        controller = WindowsController(app_finder=MagicMock())
        self.assertFalse(controller.press_key(controller.VK_VOLUME_UP))

    def test_lock_workstation_returns_false_without_windll(self):
        controller = WindowsController(app_finder=MagicMock())
        self.assertFalse(controller.lock_workstation())


class PowerActionTests(unittest.TestCase):
    def setUp(self):
        self.controller = WindowsController(app_finder=MagicMock())

    def test_power_action_dispatches_to_handler(self):
        self.controller.shutdown_pc = MagicMock(return_value=True)
        self.assertTrue(self.controller.power_action("shutdown"))
        self.controller.shutdown_pc.assert_called_once()

    def test_power_action_unknown_target(self):
        self.assertFalse(self.controller.power_action("dance"))

    @patch("core.windows_controller.subprocess.run")
    def test_shutdown_invokes_shutdown_command(self, mock_run):
        mock_run.return_value = MagicMock()
        self.assertTrue(self.controller.shutdown_pc())
        args = mock_run.call_args[0][0]
        self.assertIn("/s", args)

    @patch("core.windows_controller.subprocess.run")
    def test_restart_invokes_shutdown_command_with_r(self, mock_run):
        mock_run.return_value = MagicMock()
        self.assertTrue(self.controller.restart_pc())
        args = mock_run.call_args[0][0]
        self.assertIn("/r", args)

    @patch("core.windows_controller.subprocess.run", side_effect=OSError("no such file"))
    def test_shutdown_failure_returns_false(self, mock_run):
        self.assertFalse(self.controller.shutdown_pc())


class BrightnessTests(unittest.TestCase):
    def setUp(self):
        self.controller = WindowsController(app_finder=MagicMock())

    @patch("core.windows_controller.subprocess.run")
    def test_set_brightness_clamped_and_invoked(self, mock_run):
        mock_run.return_value = MagicMock(returncode=0)
        self.assertTrue(self.controller.set_brightness(150))  # clamped to 100
        command = mock_run.call_args[0][0][-1]
        self.assertIn("100", command)

    @patch("core.windows_controller.subprocess.run", side_effect=OSError("nope"))
    def test_set_brightness_failure(self, mock_run):
        self.assertFalse(self.controller.set_brightness(50))


class CloseAppTests(unittest.TestCase):
    def setUp(self):
        app_finder = MagicMock()
        app_finder.find.return_value = {}
        self.controller = WindowsController(app_finder=app_finder)

    @patch("core.windows_controller.psutil.process_iter")
    @patch("core.windows_controller.psutil.Process")
    def test_close_app_terminates_matching_process(self, mock_process_cls, mock_iter):
        mock_iter.return_value = [MagicMock(info={"pid": 123, "name": "notepad.exe"})]

        handle = MagicMock()
        mock_process_cls.return_value = handle

        self.assertTrue(self.controller.close_app("notepad"))
        handle.terminate.assert_called_once()

    @patch("core.windows_controller.psutil.process_iter", return_value=[])
    def test_close_app_no_match_returns_false(self, mock_iter):
        self.assertFalse(self.controller.close_app("programa_inexistente"))

    def test_close_app_empty_target(self):
        self.assertFalse(self.controller.close_app(""))


class SiteAndFolderTests(unittest.TestCase):
    def setUp(self):
        self.controller = WindowsController(app_finder=MagicMock())

    @patch("core.windows_controller.webbrowser.open_new_tab")
    def test_open_known_site(self, mock_open):
        self.assertTrue(self.controller.open_site("youtube"))
        mock_open.assert_called_once_with("https://www.youtube.com")

    @patch("core.windows_controller.webbrowser.open_new_tab")
    def test_open_raw_domain(self, mock_open):
        self.assertTrue(self.controller.open_site("example.com"))
        mock_open.assert_called_once_with("https://example.com")

    def test_open_site_unresolvable(self):
        self.assertFalse(self.controller.open_site("um monte de palavras soltas"))


if __name__ == "__main__":
    unittest.main()
