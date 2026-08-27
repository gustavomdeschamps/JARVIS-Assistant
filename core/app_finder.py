import json
import os
import re
import subprocess
import time
import unicodedata
import winreg

from dataclasses import (
    asdict,
    dataclass
)

from difflib import SequenceMatcher

from pathlib import Path

from config import (
    APP_CACHE_HOURS,
    DATA_DIR
)


@dataclass
class AppEntry:

    name: str

    path: str

    source: str


class AppFinder:

    def __init__(
        self
    ):

        self.cache_file = (
            DATA_DIR
            /
            "apps_index.json"
        )


        self.apps = []

        self._keys = set()


        if not self._load_cache():

            self.rebuild_index()


    # =========================================================
    # NORMALIZE
    # =========================================================

    def normalize(
        self,
        text
    ):

        if not text:

            return ""


        text = (
            str(
                text
            )
            .lower()
            .strip()
        )


        text = "".join(

            character

            for character in (
                unicodedata
                .normalize(
                    "NFD",
                    text
                )
            )

            if (
                unicodedata.category(
                    character
                )
                !=
                "Mn"
            )
        )


        text = (
            text
            .replace(
                "_",
                " "
            )
            .replace(
                "-",
                " "
            )
        )


        text = re.sub(

            r"[^a-z0-9 ]+",

            " ",

            text
        )


        return re.sub(

            r"\s+",

            " ",

            text

        ).strip()


    # =========================================================
    # CACHE
    # =========================================================

    def _cache_fresh(
        self
    ):

        try:

            age = (

                time.time()

                -

                self.cache_file
                .stat()
                .st_mtime
            )


            return (

                age

                <

                APP_CACHE_HOURS
                *
                3600
            )


        except Exception:

            return False


    def _load_cache(
        self
    ):

        if not self._cache_fresh():

            return False


        try:

            raw = json.loads(

                self.cache_file
                .read_text(
                    encoding="utf-8"
                )
            )


            if not isinstance(
                raw,
                list
            ):

                return False


            for item in raw:

                if not isinstance(
                    item,
                    dict
                ):

                    continue


                self.add_app(

                    item.get(
                        "name"
                    ),

                    item.get(
                        "path"
                    ),

                    item.get(
                        "source",
                        "cache"
                    )
                )


            return bool(
                self.apps
            )


        except Exception:

            return False


    def _save_cache(
        self
    ):

        try:

            self.cache_file.write_text(

                json.dumps(

                    [
                        asdict(
                            app
                        )

                        for app in self.apps
                    ],

                    ensure_ascii=False,

                    indent=2
                ),

                encoding="utf-8"
            )


        except Exception:

            pass


    # =========================================================
    # ADD
    # =========================================================

    def add_app(
        self,
        name,
        path,
        source
    ):

        if not name or not path:

            return


        name = str(
            name
        ).strip()


        path = str(
            path
        ).strip()


        normalized = (
            self.normalize(
                name
            )
        )


        if not normalized:

            return


        ignored = [

            "uninstall",

            "uninstaller",

            "desinstalar",

            "update",

            "updater",

            "repair",

            "crash reporter"
        ]


        if any(

            value
            in
            normalized

            for value in ignored

        ):

            return


        key = (

            normalized,

            path.lower()
        )


        if key in self._keys:

            return


        self._keys.add(
            key
        )


        self.apps.append(

            AppEntry(

                name=name,

                path=path,

                source=source
            )
        )


    # =========================================================
    # REBUILD
    # =========================================================

    def rebuild_index(
        self
    ):

        print(
            "[APPS] Criando índice..."
        )


        self.apps.clear()

        self._keys.clear()


        self.scan_start_apps()

        self.scan_start_menu()

        self.scan_desktop()

        self.scan_registry()

        self.scan_path()


        self._save_cache()


        print(
            f"[APPS] "
            f"{len(self.apps)} "
            f"entradas indexadas."
        )


        return len(
            self.apps
        )


    # =========================================================
    # START APPS
    # =========================================================

    def scan_start_apps(
        self
    ):

        command = (

            "Get-StartApps | "

            "Select-Object "
            "Name,AppID | "

            "ConvertTo-Json -Compress"
        )


        try:

            result = subprocess.run(

                [
                    "powershell.exe",

                    "-NoProfile",

                    "-ExecutionPolicy",
                    "Bypass",

                    "-Command",
                    command
                ],

                capture_output=True,

                text=True,

                encoding="utf-8",

                errors="ignore",

                timeout=12
            )


            output = (
                result
                .stdout
                .strip()
            )


            if not output:

                return


            data = json.loads(
                output
            )


            if isinstance(
                data,
                dict
            ):

                data = [
                    data
                ]


            for item in data:

                if not isinstance(
                    item,
                    dict
                ):

                    continue


                name = item.get(
                    "Name"
                )


                app_id = item.get(
                    "AppID"
                )


                if name and app_id:

                    self.add_app(

                        name,

                        (
                            "shell:AppsFolder\\"
                            +
                            str(
                                app_id
                            )
                        ),

                        "StartApps"
                    )


        except Exception:

            pass


    # =========================================================
    # START MENU
    # =========================================================

    def scan_start_menu(
        self
    ):

        roots = []


        appdata = (
            os.getenv(
                "APPDATA"
            )
        )


        programdata = (
            os.getenv(
                "PROGRAMDATA"
            )
        )


        if appdata:

            roots.append(

                Path(
                    appdata
                )
                /
                "Microsoft"
                /
                "Windows"
                /
                "Start Menu"
                /
                "Programs"
            )


        if programdata:

            roots.append(

                Path(
                    programdata
                )
                /
                "Microsoft"
                /
                "Windows"
                /
                "Start Menu"
                /
                "Programs"
            )


        for root in roots:

            self._scan_shortcuts(
                root,
                "StartMenu"
            )


    # =========================================================
    # DESKTOP
    # =========================================================

    def scan_desktop(
        self
    ):

        roots = [

            Path.home()
            /
            "Desktop"
        ]


        public = os.getenv(
            "PUBLIC"
        )


        onedrive = os.getenv(
            "OneDrive"
        )


        if public:

            roots.append(

                Path(
                    public
                )
                /
                "Desktop"
            )


        if onedrive:

            roots.append(

                Path(
                    onedrive
                )
                /
                "Desktop"
            )


        for root in roots:

            self._scan_shortcuts(
                root,
                "Desktop"
            )


    # =========================================================
    # SHORTCUTS
    # =========================================================

    def _scan_shortcuts(
        self,
        root,
        source
    ):

        try:

            if not root.exists():

                return


            for pattern in [

                "*.lnk",

                "*.url"
            ]:

                for path in root.rglob(
                    pattern
                ):

                    self.add_app(

                        path.stem,

                        str(
                            path
                        ),

                        source
                    )


        except Exception:

            pass


    # =========================================================
    # REGISTRY
    # =========================================================

    def scan_registry(
        self
    ):

        registry_path = (

            r"SOFTWARE\Microsoft\Windows"
            r"\CurrentVersion\App Paths"
        )


        roots = [

            (
                winreg.HKEY_CURRENT_USER,
                0
            ),

            (
                winreg.HKEY_LOCAL_MACHINE,
                winreg.KEY_WOW64_64KEY
            ),

            (
                winreg.HKEY_LOCAL_MACHINE,
                winreg.KEY_WOW64_32KEY
            )
        ]


        for (
            root,
            flags
        ) in roots:

            try:

                key = winreg.OpenKey(

                    root,

                    registry_path,

                    0,

                    winreg.KEY_READ
                    |
                    flags
                )


            except Exception:

                continue


            index = 0


            while True:

                try:

                    sub_name = (
                        winreg
                        .EnumKey(
                            key,
                            index
                        )
                    )


                    index += 1


                except OSError:

                    break


                try:

                    subkey = (
                        winreg
                        .OpenKey(
                            key,
                            sub_name
                        )
                    )


                    value, _ = (
                        winreg
                        .QueryValueEx(
                            subkey,
                            ""
                        )
                    )


                    value = (

                        os.path
                        .expandvars(
                            str(
                                value
                            )
                        )
                        .strip(
                            '"'
                        )
                    )


                    name = sub_name


                    if name.lower().endswith(
                        ".exe"
                    ):

                        name = name[
                            :-4
                        ]


                    self.add_app(

                        name,

                        value,

                        "Registry"
                    )


                    self.add_app(

                        Path(
                            value
                        ).stem,

                        value,

                        "Registry"
                    )


                except Exception:

                    pass


    # =========================================================
    # PATH
    # =========================================================

    def scan_path(
        self
    ):

        for directory in (

            os.getenv(
                "PATH",
                ""
            )
            .split(
                os.pathsep
            )

        ):

            try:

                root = Path(
                    directory
                )


                if (

                    not root.exists()

                    or

                    not root.is_dir()

                ):

                    continue


                for exe in root.glob(
                    "*.exe"
                ):

                    self.add_app(

                        exe.stem,

                        str(
                            exe
                        ),

                        "PATH"
                    )


            except Exception:

                pass


    # =========================================================
    # NAMES
    # =========================================================

    def names(
        self,
        limit=None
    ):

        seen = set()

        result = []


        for app in self.apps:

            normalized = (
                self.normalize(
                    app.name
                )
            )


            if normalized in seen:

                continue


            seen.add(
                normalized
            )


            result.append(
                app.name
            )


            if (

                limit

                and

                len(
                    result
                )
                >=
                limit

            ):

                break


        return result


    # =========================================================
    # ALIASES
    # =========================================================

    def _aliases(
        self,
        query
    ):

        normalized = (
            self.normalize(
                query
            )
        )


        aliases = {

            "vscode":
                "visual studio code",

            "vs code":
                "visual studio code",

            "visual studio codigo":
                "visual studio code",

            "code":
                "visual studio code",

            "editor de codigo":
                "visual studio code",

            "programa de codigo":
                "visual studio code",

            "discordia":
                "discord",

            "cromo":
                "chrome",

            "google chrome":
                "chrome"
        }


        return aliases.get(

            normalized,

            normalized
        )


    # =========================================================
    # SCORE
    # =========================================================

    def _score(
        self,
        query,
        name
    ):

        query = self.normalize(
            query
        )


        name = self.normalize(
            name
        )


        if not query or not name:

            return 0.0


        if query == name:

            return 1.0


        if name.startswith(
            query
        ):

            return 0.96


        if query in name:

            return 0.92


        if name in query:

            return 0.88


        sequence = (
            SequenceMatcher(
                None,
                query,
                name
            )
            .ratio()
        )


        q_words = set(
            query.split()
        )


        n_words = set(
            name.split()
        )


        overlap = (

            len(
                q_words
                &
                n_words
            )

            /

            max(
                len(
                    q_words
                ),

                len(
                    n_words
                ),

                1
            )
        )


        return max(

            sequence,

            overlap
            *
            0.95
        )


    # =========================================================
    # FIND
    # =========================================================

    def find(
        self,
        query
    ):

        query = (
            self._aliases(
                query
            )
        )


        best = None

        best_score = 0.0


        for app in self.apps:

            score = self._score(

                query,

                app.name
            )


            if score > best_score:

                best = app

                best_score = score


        if best_score < 0.58:

            return (
                None,
                best_score
            )


        return (
            best,
            best_score
        )


    # =========================================================
    # LAUNCH
    # =========================================================

    def launch(
        self,
        query
    ):

        app, confidence = (
            self.find(
                query
            )
        )


        if app is None:

            return {

                "success":
                    False,

                "name":
                    "",

                "score":
                    confidence
            }


        try:

            if app.path.startswith(
                "shell:AppsFolder\\"
            ):

                subprocess.Popen(

                    [
                        "explorer.exe",

                        app.path
                    ]
                )


            else:

                os.startfile(
                    app.path
                )


            return {

                "success":
                    True,

                "name":
                    app.name,

                "score":
                    confidence
            }


        except Exception as error:

            print(
                f"[APPS] "
                f"Falha ao abrir "
                f"{app.name}: "
                f"{error}"
            )


            return {

                "success":
                    False,

                "name":
                    app.name,

                "score":
                    confidence
            }