import ctypes
import os
import subprocess
import time
import unicodedata
import webbrowser

from pathlib import Path
from urllib.parse import quote_plus

import psutil


class WindowsController:

    # =========================================================
    # WINDOWS MEDIA KEYS
    # =========================================================

    VK_VOLUME_MUTE = 0xAD

    VK_VOLUME_DOWN = 0xAE

    VK_VOLUME_UP = 0xAF

    VK_MEDIA_NEXT_TRACK = 0xB0

    VK_MEDIA_PREV_TRACK = 0xB1

    VK_MEDIA_PLAY_PAUSE = 0xB3

    KEYEVENTF_KEYUP = 0x0002


    def __init__(
        self,
        app_finder
    ):

        self.app_finder = app_finder


        self.user32 = (
            ctypes
            .windll
            .user32
        )


    # =========================================================
    # NORMALIZAR
    # =========================================================

    def normalize(
        self,
        text
    ):

        if not text:

            return ""


        text = (
            str(text)
            .lower()
            .strip()
        )


        return "".join(

            character

            for character in unicodedata.normalize(
                "NFD",
                text
            )

            if unicodedata.category(
                character
            )
            !=
            "Mn"
        )


    # =========================================================
    # APP
    # =========================================================

    def open_app(
        self,
        target
    ):

        if not target:

            return False


        normalized = self.normalize(
            target
        )


        print(
            f"[WINDOWS] Procurando aplicativo: {target}"
        )


        # =====================================================
        # APPS NATIVOS
        # =====================================================

        builtins = {

            "calculadora": [
                "calc.exe"
            ],

            "calculator": [
                "calc.exe"
            ],

            "bloco de notas": [
                "notepad.exe"
            ],

            "notepad": [
                "notepad.exe"
            ],

            "explorador": [
                "explorer.exe"
            ],

            "explorador de arquivos": [
                "explorer.exe"
            ],

            "arquivos": [
                "explorer.exe"
            ],

            "gerenciador de tarefas": [
                "taskmgr.exe"
            ],

            "paint": [
                "mspaint.exe"
            ],

            "prompt de comando": [
                "cmd.exe"
            ],

            "cmd": [
                "cmd.exe"
            ],

            "powershell": [
                "powershell.exe"
            ],

            "terminal": [
                "wt.exe",
                "powershell.exe"
            ]
        }


        if normalized in builtins:

            for executable in builtins[
                normalized
            ]:

                try:

                    subprocess.Popen(
                        [
                            executable
                        ]
                    )


                    return True


                except Exception:

                    continue


        # =====================================================
        # APP FINDER
        # =====================================================

        result = (
            self.app_finder
            .launch(
                target
            )
        )


        return bool(
            result.get(
                "success",
                False
            )
        )


    # =========================================================
    # SITE
    # =========================================================

    def open_site(
        self,
        target
    ):

        if not target:

            return False


        normalized = self.normalize(
            target
        )


        sites = {

            "youtube":
                "https://www.youtube.com",

            "google":
                "https://www.google.com",

            "github":
                "https://github.com",

            "gmail":
                "https://mail.google.com",

            "whatsapp":
                "https://web.whatsapp.com",

            "whatsapp web":
                "https://web.whatsapp.com",

            "reddit":
                "https://www.reddit.com",

            "netflix":
                "https://www.netflix.com",

            "chatgpt":
                "https://chatgpt.com"
        }


        url = sites.get(
            normalized
        )


        if url:

            webbrowser.open_new_tab(
                url
            )


            return True


        # =====================================================
        # URL RECEBIDA DIRETAMENTE
        # =====================================================

        if (
            "." in normalized
            and
            " " not in normalized
        ):

            url = normalized


            if not url.startswith(
                (
                    "http://",
                    "https://"
                )
            ):

                url = (
                    "https://"
                    +
                    url
                )


            webbrowser.open_new_tab(
                url
            )


            return True


        return False


    # =========================================================
    # PASTA
    # =========================================================

    def open_folder(
        self,
        target
    ):

        if not target:

            return False


        normalized = self.normalize(
            target
        )


        home = Path.home()


        one_drive_string = os.getenv(
            "OneDrive"
        )


        one_drive = (

            Path(
                one_drive_string
            )

            if one_drive_string

            else None
        )


        candidates = {

            "downloads": [
                home / "Downloads"
            ],

            "download": [
                home / "Downloads"
            ],

            "documentos": [
                home / "Documents",

                (
                    one_drive / "Documents"
                    if one_drive
                    else None
                )
            ],

            "documents": [
                home / "Documents",

                (
                    one_drive / "Documents"
                    if one_drive
                    else None
                )
            ],

            "desktop": [
                home / "Desktop",

                (
                    one_drive / "Desktop"
                    if one_drive
                    else None
                )
            ],

            "area de trabalho": [
                home / "Desktop",

                (
                    one_drive / "Desktop"
                    if one_drive
                    else None
                )
            ],

            "imagens": [
                home / "Pictures"
            ],

            "pictures": [
                home / "Pictures"
            ],

            "fotos": [
                home / "Pictures"
            ],

            "musicas": [
                home / "Music"
            ],

            "music": [
                home / "Music"
            ],

            "videos": [
                home / "Videos"
            ],

            "usuario": [
                home
            ],

            "home": [
                home
            ]
        }


        paths = candidates.get(
            normalized,
            []
        )


        for path in paths:

            if path is None:

                continue


            try:

                if path.exists():

                    os.startfile(
                        str(
                            path
                        )
                    )


                    return True


            except Exception:

                continue


        # =====================================================
        # CAMINHO REAL
        # =====================================================

        try:

            real_path = Path(
                target
            )


            if real_path.exists():

                os.startfile(
                    str(
                        real_path
                    )
                )


                return True


        except Exception:

            pass


        return False


    # =========================================================
    # SETTINGS
    # =========================================================

    def open_settings(
        self
    ):

        try:

            os.startfile(
                "ms-settings:"
            )


            return True


        except Exception:

            return False


    # =========================================================
    # GOOGLE
    # =========================================================

    def search_web(
        self,
        query
    ):

        if not query:

            return False


        url = (

            "https://www.google.com/search?q="

            +

            quote_plus(
                query
            )
        )


        webbrowser.open_new_tab(
            url
        )


        return True


    # =========================================================
    # YOUTUBE
    # =========================================================

    def search_youtube(
        self,
        query
    ):

        if not query:

            return False


        url = (

            "https://www.youtube.com/results?search_query="

            +

            quote_plus(
                query
            )
        )


        webbrowser.open_new_tab(
            url
        )


        return True


    # =========================================================
    # TECLA
    # =========================================================

    def press_key(
        self,
        virtual_key
    ):

        self.user32.keybd_event(
            virtual_key,
            0,
            0,
            0
        )


        self.user32.keybd_event(
            virtual_key,
            0,
            self.KEYEVENTF_KEYUP,
            0
        )


    # =========================================================
    # VOLUME
    # =========================================================

    def volume_up(
        self,
        amount=4
    ):

        amount = max(
            1,
            min(
                int(
                    amount or 4
                ),
                20
            )
        )


        for _ in range(
            amount
        ):

            self.press_key(
                self.VK_VOLUME_UP
            )


            time.sleep(
                0.015
            )


        return True


    def volume_down(
        self,
        amount=4
    ):

        amount = max(
            1,
            min(
                int(
                    amount or 4
                ),
                20
            )
        )


        for _ in range(
            amount
        ):

            self.press_key(
                self.VK_VOLUME_DOWN
            )


            time.sleep(
                0.015
            )


        return True


    def volume_mute(
        self
    ):

        self.press_key(
            self.VK_VOLUME_MUTE
        )


        return True


    # =========================================================
    # MEDIA
    # =========================================================

    def media_play_pause(
        self
    ):

        self.press_key(
            self.VK_MEDIA_PLAY_PAUSE
        )


        return True


    def media_next(
        self
    ):

        self.press_key(
            self.VK_MEDIA_NEXT_TRACK
        )


        return True


    def media_previous(
        self
    ):

        self.press_key(
            self.VK_MEDIA_PREV_TRACK
        )


        return True


    # =========================================================
    # SYSTEM INFO
    # =========================================================

    def system_info(
        self,
        target
    ):

        normalized = self.normalize(
            target
        )


        # =====================================================
        # RAM
        # =====================================================

        if normalized in [
            "ram",
            "memoria",
            "memoria ram"
        ]:

            memory = (
                psutil
                .virtual_memory()
            )


            return (

                f"O computador está usando "
                f"aproximadamente "
                f"{round(memory.percent)} por cento "
                f"da memória RAM."
            )


        # =====================================================
        # CPU
        # =====================================================

        if normalized in [
            "cpu",
            "processador"
        ]:

            usage = (
                psutil
                .cpu_percent(
                    interval=0.15
                )
            )


            return (

                f"O processador está usando "
                f"aproximadamente "
                f"{round(usage)} por cento."
            )


        # =====================================================
        # DISK
        # =====================================================

        if normalized in [
            "disk",
            "disco",
            "ssd",
            "armazenamento",
            "espaco"
        ]:

            drive = (

                os.getenv(
                    "SystemDrive",
                    "C:"
                )

                +
                "\\"
            )


            disk = psutil.disk_usage(
                drive
            )


            gigabyte = (
                1024
                *
                1024
                *
                1024
            )


            free = round(
                disk.free
                /
                gigabyte,
                1
            )


            total = round(
                disk.total
                /
                gigabyte,
                1
            )


            return (

                f"Você tem aproximadamente "
                f"{free} gigabytes livres "
                f"de {total} gigabytes."
            )


        return (
            "Não identifiquei qual informação do computador você quer."
        )