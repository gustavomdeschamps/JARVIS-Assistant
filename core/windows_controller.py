"""Everything that actually reaches out and touches the operating system.

This is the one module allowed to call ``subprocess``, ``os.startfile``,
``ctypes.windll`` and friends — keeping all of that in one place means the
rest of the app (the brain, the command router, the UI) never has to know
*how* an app gets opened or the screen gets locked, only *that* it did.

Windows-only APIs (``ctypes.windll``) are accessed defensively: on any
other platform (useful for running the unit tests, or developing parts of
this project from Linux/macOS) the controller still imports and
constructs cleanly, it just reports those specific actions as
unavailable instead of crashing at import time.
"""

import ctypes
import os
import subprocess
import time
import unicodedata
import webbrowser
from pathlib import Path
from urllib.parse import quote_plus

import psutil

from config import SCREENSHOTS_DIR
from core.logger import get_logger

logger = get_logger(__name__)

_SUBPROCESS_TIMEOUT = 8


class WindowsController:

    # =========================================================
    # WINDOWS MEDIA / VOLUME VIRTUAL KEYS
    # =========================================================

    VK_VOLUME_MUTE = 0xAD
    VK_VOLUME_DOWN = 0xAE
    VK_VOLUME_UP = 0xAF
    VK_MEDIA_NEXT_TRACK = 0xB0
    VK_MEDIA_PREV_TRACK = 0xB1
    VK_MEDIA_PLAY_PAUSE = 0xB3
    KEYEVENTF_KEYUP = 0x0002

    POWER_ACTIONS = ("lock", "sleep", "shutdown", "restart")

    def __init__(self, app_finder):
        self.app_finder = app_finder
        self.user32 = self._load_user32()

    def _load_user32(self):
        try:
            return ctypes.windll.user32
        except AttributeError:
            logger.warning(
                "ctypes.windll indisponível (sistema não é Windows). "
                "Ações de teclado/energia ficarão desativadas."
            )
            return None

    # =========================================================
    # NORMALIZAR
    # =========================================================

    def normalize(self, text):
        if not text:
            return ""

        text = str(text).lower().strip()

        return "".join(
            character
            for character in unicodedata.normalize("NFD", text)
            if unicodedata.category(character) != "Mn"
        )

    # =========================================================
    # APP
    # =========================================================

    _BUILTIN_APPS = {
        "calculadora": ["calc.exe"],
        "calculator": ["calc.exe"],
        "bloco de notas": ["notepad.exe"],
        "notepad": ["notepad.exe"],
        "explorador": ["explorer.exe"],
        "explorador de arquivos": ["explorer.exe"],
        "arquivos": ["explorer.exe"],
        "gerenciador de tarefas": ["taskmgr.exe"],
        "paint": ["mspaint.exe"],
        "prompt de comando": ["cmd.exe"],
        "cmd": ["cmd.exe"],
        "powershell": ["powershell.exe"],
        "terminal": ["wt.exe", "powershell.exe"],
    }

    def open_app(self, target):
        if not target:
            return False

        normalized = self.normalize(target)
        logger.info("Procurando aplicativo: %s", target)

        for executable in self._BUILTIN_APPS.get(normalized, []):
            try:
                subprocess.Popen([executable])
                return True
            except Exception:
                continue

        result = self.app_finder.launch(target)
        return bool(result.get("success", False))

    # =========================================================
    # FECHAR APP
    # =========================================================

    def close_app(self, target):
        if not target:
            return False

        normalized = self.normalize(target)
        builtin_names = {
            self.normalize(exe).replace(".exe", "")
            for names in self._BUILTIN_APPS.values()
            for exe in names
        }

        candidates = {normalized} | (
            {normalized} if normalized in builtin_names else set()
        )

        # Also try to resolve through the app index, so "fecha o chrome"
        # matches the real process name even if it differs from the
        # spoken name (e.g. "vs code" -> "Code.exe").
        try:
            match = self.app_finder.find(target)
            if match and match.get("path"):
                exe_name = Path(match["path"]).stem
                candidates.add(self.normalize(exe_name))
        except Exception:
            pass

        closed_any = False

        for process in psutil.process_iter(["pid", "name"]):
            try:
                proc_name = self.normalize(Path(process.info["name"] or "").stem)
            except Exception:
                continue

            if not proc_name:
                continue

            if proc_name in candidates or any(
                candidate and candidate in proc_name for candidate in candidates
            ):
                try:
                    handle = psutil.Process(process.info["pid"])
                    handle.terminate()

                    try:
                        handle.wait(timeout=3)
                    except psutil.TimeoutExpired:
                        handle.kill()

                    closed_any = True
                    logger.info("Encerrado processo %s (pid %s).", proc_name, process.info["pid"])

                except (psutil.NoSuchProcess, psutil.AccessDenied) as error:
                    logger.debug("Não foi possível encerrar %s: %s", proc_name, error)

        return closed_any

    # =========================================================
    # SITE
    # =========================================================

    _SITES = {
        "youtube": "https://www.youtube.com",
        "google": "https://www.google.com",
        "github": "https://github.com",
        "gmail": "https://mail.google.com",
        "whatsapp": "https://web.whatsapp.com",
        "whatsapp web": "https://web.whatsapp.com",
        "reddit": "https://www.reddit.com",
        "netflix": "https://www.netflix.com",
        "chatgpt": "https://chatgpt.com",
        "spotify": "https://open.spotify.com",
        "twitter": "https://x.com",
        "x": "https://x.com",
        "instagram": "https://www.instagram.com",
        "linkedin": "https://www.linkedin.com",
        "amazon": "https://www.amazon.com.br",
    }

    def open_site(self, target):
        if not target:
            return False

        normalized = self.normalize(target)

        url = self._SITES.get(normalized)
        if url:
            webbrowser.open_new_tab(url)
            return True

        # URL recebida diretamente (ex: "meusite.com.br").
        if "." in normalized and " " not in normalized:
            url = normalized
            if not url.startswith(("http://", "https://")):
                url = "https://" + url

            webbrowser.open_new_tab(url)
            return True

        return False

    # =========================================================
    # PASTA
    # =========================================================

    def open_folder(self, target):
        if not target:
            return False

        normalized = self.normalize(target)
        home = Path.home()

        one_drive_string = os.getenv("OneDrive")
        one_drive = Path(one_drive_string) if one_drive_string else None

        def _with_onedrive(name):
            paths = [home / name]
            if one_drive:
                paths.append(one_drive / name)
            return paths

        candidates = {
            "downloads": _with_onedrive("Downloads"),
            "download": _with_onedrive("Downloads"),
            "documentos": _with_onedrive("Documents"),
            "documents": _with_onedrive("Documents"),
            "desktop": _with_onedrive("Desktop"),
            "area de trabalho": _with_onedrive("Desktop"),
            "imagens": [home / "Pictures"],
            "pictures": [home / "Pictures"],
            "fotos": [home / "Pictures"],
            "musicas": [home / "Music"],
            "music": [home / "Music"],
            "videos": [home / "Videos"],
            "usuario": [home],
            "home": [home],
        }

        for path in candidates.get(normalized, []):
            if path is None:
                continue

            try:
                if path.exists():
                    os.startfile(str(path))
                    return True
            except Exception:
                continue

        # Caminho real recebido diretamente.
        try:
            real_path = Path(target)
            if real_path.exists():
                os.startfile(str(real_path))
                return True
        except Exception:
            pass

        return False

    # =========================================================
    # SETTINGS
    # =========================================================

    def open_settings(self):
        try:
            os.startfile("ms-settings:")
            return True
        except Exception:
            return False

    # =========================================================
    # WEB / YOUTUBE
    # =========================================================

    def search_web(self, query):
        if not query:
            return False

        webbrowser.open_new_tab("https://www.google.com/search?q=" + quote_plus(query))
        return True

    def search_youtube(self, query):
        if not query:
            return False

        webbrowser.open_new_tab(
            "https://www.youtube.com/results?search_query=" + quote_plus(query)
        )
        return True

    # =========================================================
    # TECLA
    # =========================================================

    def press_key(self, virtual_key):
        if self.user32 is None:
            logger.debug("press_key ignorado: sem acesso a ctypes.windll.")
            return False

        self.user32.keybd_event(virtual_key, 0, 0, 0)
        self.user32.keybd_event(virtual_key, 0, self.KEYEVENTF_KEYUP, 0)
        return True

    # =========================================================
    # VOLUME
    # =========================================================

    def volume_up(self, amount=4):
        amount = max(1, min(int(amount or 4), 20))
        for _ in range(amount):
            self.press_key(self.VK_VOLUME_UP)
            time.sleep(0.015)
        return True

    def volume_down(self, amount=4):
        amount = max(1, min(int(amount or 4), 20))
        for _ in range(amount):
            self.press_key(self.VK_VOLUME_DOWN)
            time.sleep(0.015)
        return True

    def volume_mute(self):
        return self.press_key(self.VK_VOLUME_MUTE)

    # =========================================================
    # MEDIA
    # =========================================================

    def media_play_pause(self):
        return self.press_key(self.VK_MEDIA_PLAY_PAUSE)

    def media_next(self):
        return self.press_key(self.VK_MEDIA_NEXT_TRACK)

    def media_previous(self):
        return self.press_key(self.VK_MEDIA_PREV_TRACK)

    # =========================================================
    # BRILHO
    # =========================================================

    def set_brightness(self, percent):
        percent = max(0, min(int(percent), 100))

        command = (
            "(Get-WmiObject -Namespace root/WMI "
            "-Class WmiMonitorBrightnessMethods)"
            f".WmiSetBrightness(1,{percent})"
        )

        try:
            result = subprocess.run(
                ["powershell", "-NoProfile", "-Command", command],
                capture_output=True,
                timeout=_SUBPROCESS_TIMEOUT,
            )
            return result.returncode == 0
        except Exception as error:
            logger.warning("Não foi possível ajustar o brilho: %s", error)
            return False

    # =========================================================
    # SCREENSHOT
    # =========================================================

    def take_screenshot(self):
        try:
            from PIL import ImageGrab
        except ImportError:
            logger.error(
                "Pillow não está instalado — rode 'pip install Pillow' "
                "para habilitar capturas de tela."
            )
            return None

        try:
            SCREENSHOTS_DIR.mkdir(parents=True, exist_ok=True)
            filename = SCREENSHOTS_DIR / f"jarvis-{int(time.time())}.png"

            image = ImageGrab.grab()
            image.save(filename)

            return str(filename)
        except Exception as error:
            logger.error("Falha ao capturar a tela: %s", error)
            return None

    # =========================================================
    # ENERGIA (bloquear / suspender / desligar / reiniciar)
    # =========================================================
    #
    # NOTA DE SEGURANÇA: shutdown/restart são irreversíveis e podem
    # derrubar trabalho não salvo do usuário. Este módulo apenas executa
    # a ação recebida — a decisão de exigir confirmação antes de chamar
    # `power_action("shutdown"/"restart", ...)` é responsabilidade do
    # CommandSystem (ver core/commands.py), nunca deste controlador.

    def lock_workstation(self):
        if self.user32 is None:
            logger.debug("lock_workstation ignorado: sem acesso a ctypes.windll.")
            return False

        try:
            return bool(self.user32.LockWorkStation())
        except Exception as error:
            logger.warning("Falha ao bloquear a tela: %s", error)
            return False

    def sleep_pc(self):
        try:
            subprocess.run(
                ["rundll32.exe", "powrprof.dll,SetSuspendState", "0,1,0"],
                timeout=_SUBPROCESS_TIMEOUT,
            )
            return True
        except Exception as error:
            logger.warning("Falha ao suspender o computador: %s", error)
            return False

    def shutdown_pc(self):
        try:
            subprocess.run(["shutdown", "/s", "/t", "0"], timeout=_SUBPROCESS_TIMEOUT)
            return True
        except Exception as error:
            logger.warning("Falha ao desligar o computador: %s", error)
            return False

    def restart_pc(self):
        try:
            subprocess.run(["shutdown", "/r", "/t", "0"], timeout=_SUBPROCESS_TIMEOUT)
            return True
        except Exception as error:
            logger.warning("Falha ao reiniciar o computador: %s", error)
            return False

    def power_action(self, action):
        action = self.normalize(action)

        handlers = {
            "lock": self.lock_workstation,
            "sleep": self.sleep_pc,
            "shutdown": self.shutdown_pc,
            "restart": self.restart_pc,
        }

        handler = handlers.get(action)
        if handler is None:
            return False

        return handler()

    # =========================================================
    # SYSTEM INFO (fallback simples, sem SystemScanner)
    # =========================================================

    def system_info(self, target):
        normalized = self.normalize(target)

        if normalized in ["ram", "memoria", "memoria ram"]:
            memory = psutil.virtual_memory()
            return (
                f"O computador está usando aproximadamente "
                f"{round(memory.percent)} por cento da memória RAM."
            )

        if normalized in ["cpu", "processador"]:
            usage = psutil.cpu_percent(interval=0.15)
            return f"O processador está usando aproximadamente {round(usage)} por cento."

        if normalized in ["disk", "disco", "ssd", "armazenamento", "espaco"]:
            drive = os.getenv("SystemDrive", "C:") + "\\"
            disk = psutil.disk_usage(drive)
            gigabyte = 1024 * 1024 * 1024

            free = round(disk.free / gigabyte, 1)
            total = round(disk.total / gigabyte, 1)

            return f"Você tem aproximadamente {free} gigabytes livres de {total} gigabytes."

        return "Não identifiquei qual informação do computador você quer."
