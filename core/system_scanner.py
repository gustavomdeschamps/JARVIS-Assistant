import json
import os
import platform
import socket
import subprocess
import time

from pathlib import Path

import psutil

from config import (
    DATA_DIR,
    SYSTEM_CACHE_MINUTES
)


class SystemScanner:

    def __init__(
        self
    ):

        self.cache_file = (
            DATA_DIR
            /
            "device_profile.json"
        )


        self.profile = {}


        self.load_or_scan()


    # =========================================================
    # POWERSHELL JSON
    # =========================================================

    def _powershell_json(
        self,
        command,
        timeout=8
    ):

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

                timeout=timeout
            )


            output = (
                result
                .stdout
                .strip()
            )


            if not output:

                return None


            return json.loads(
                output
            )


        except Exception:

            return None


    # =========================================================
    # CACHE
    # =========================================================

    def _cache_is_fresh(
        self
    ):

        try:

            age_seconds = (

                time.time()

                -

                self.cache_file
                .stat()
                .st_mtime
            )


            return (

                age_seconds

                <

                SYSTEM_CACHE_MINUTES
                *
                60
            )


        except Exception:

            return False


    def _load_cache(
        self
    ):

        try:

            data = json.loads(

                self.cache_file
                .read_text(
                    encoding="utf-8"
                )
            )


            if isinstance(
                data,
                dict
            ):

                self.profile = data

                return True


        except Exception:

            pass


        return False


    def _save_cache(
        self
    ):

        try:

            self.cache_file.write_text(

                json.dumps(

                    self.profile,

                    ensure_ascii=False,

                    indent=2
                ),

                encoding="utf-8"
            )


        except Exception:

            pass


    # =========================================================
    # LOAD
    # =========================================================

    def load_or_scan(
        self
    ):

        if (

            self._cache_is_fresh()

            and

            self._load_cache()

        ):

            return self.profile


        return self.scan(
            force=True
        )


    # =========================================================
    # SCAN
    # =========================================================

    def scan(
        self,
        force=False
    ):

        if (

            not force

            and

            self._cache_is_fresh()

            and

            self._load_cache()

        ):

            return self.profile


        print(
            "[DEVICE] Analisando notebook..."
        )


        # =====================================================
        # COMPUTADOR
        # =====================================================

        computer = (

            self._powershell_json(

                "Get-CimInstance "
                "Win32_ComputerSystem | "

                "Select-Object "
                "Manufacturer,"
                "Model,"
                "TotalPhysicalMemory | "

                "ConvertTo-Json -Compress"
            )

            or

            {}
        )


        # =====================================================
        # CPU
        # =====================================================

        cpu = (

            self._powershell_json(

                "Get-CimInstance "
                "Win32_Processor | "

                "Select-Object "
                "-First 1 "
                "Name,"
                "NumberOfCores,"
                "NumberOfLogicalProcessors,"
                "MaxClockSpeed | "

                "ConvertTo-Json -Compress"
            )

            or

            {}
        )


        # =====================================================
        # GPU
        # =====================================================

        gpu = (

            self._powershell_json(

                "Get-CimInstance "
                "Win32_VideoController | "

                "Select-Object "
                "Name,"
                "AdapterRAM,"
                "DriverVersion | "

                "ConvertTo-Json -Compress"
            )

            or

            []
        )


        if isinstance(
            gpu,
            dict
        ):

            gpu = [
                gpu
            ]


        # =====================================================
        # BIOS
        # =====================================================

        bios = (

            self._powershell_json(

                "Get-CimInstance "
                "Win32_BIOS | "

                "Select-Object "
                "Manufacturer,"
                "SMBIOSBIOSVersion | "

                "ConvertTo-Json -Compress"
            )

            or

            {}
        )


        # =====================================================
        # RAM
        # =====================================================

        memory = (
            psutil
            .virtual_memory()
        )


        # =====================================================
        # BATERIA
        # =====================================================

        battery = None


        try:

            value = (
                psutil
                .sensors_battery()
            )


            if value:

                battery = {

                    "percent":
                        round(
                            float(
                                value.percent
                            ),
                            1
                        ),

                    "plugged":
                        bool(
                            value.power_plugged
                        )
                }


        except Exception:

            battery = None


        # =====================================================
        # DISCOS
        # =====================================================

        disks = []

        seen = set()


        for partition in (
            psutil
            .disk_partitions(
                all=False
            )
        ):

            if (
                partition.mountpoint
                in
                seen
            ):

                continue


            seen.add(
                partition.mountpoint
            )


            try:

                usage = (
                    psutil
                    .disk_usage(
                        partition.mountpoint
                    )
                )


            except Exception:

                continue


            disks.append(
                {

                    "device":
                        partition.device,

                    "mountpoint":
                        partition.mountpoint,

                    "filesystem":
                        partition.fstype,

                    "total_gb":
                        round(
                            usage.total
                            /
                            (1024 ** 3),
                            1
                        ),

                    "free_gb":
                        round(
                            usage.free
                            /
                            (1024 ** 3),
                            1
                        ),

                    "used_percent":
                        round(
                            float(
                                usage.percent
                            ),
                            1
                        )
                }
            )


        # =====================================================
        # PASTAS
        # =====================================================

        home = Path.home()


        one_drive_raw = (
            os.getenv(
                "OneDrive"
            )
        )


        one_drive = (

            Path(
                one_drive_raw
            )

            if one_drive_raw

            else None
        )


        folder_candidates = {

            "home": [
                home
            ],

            "desktop": [

                home
                /
                "Desktop",

                (
                    one_drive
                    /
                    "Desktop"

                    if one_drive

                    else None
                )
            ],

            "downloads": [

                home
                /
                "Downloads"
            ],

            "documents": [

                home
                /
                "Documents",

                (
                    one_drive
                    /
                    "Documents"

                    if one_drive

                    else None
                )
            ],

            "pictures": [

                home
                /
                "Pictures",

                (
                    one_drive
                    /
                    "Pictures"

                    if one_drive

                    else None
                )
            ],

            "music": [

                home
                /
                "Music"
            ],

            "videos": [

                home
                /
                "Videos"
            ]
        }


        folders = {}


        for (
            name,
            candidates
        ) in folder_candidates.items():

            for candidate in candidates:

                if candidate is None:

                    continue


                try:

                    if candidate.exists():

                        folders[
                            name
                        ] = str(
                            candidate
                        )

                        break


                except Exception:

                    pass


        # =====================================================
        # PERFIL
        # =====================================================

        self.profile = {

            "scanned_at":
                time.time(),

            "hostname":
                socket.gethostname(),

            "manufacturer":
                computer.get(
                    "Manufacturer"
                )
                or
                "",

            "model":
                computer.get(
                    "Model"
                )
                or
                "",

            "os": {

                "name":
                    platform.system(),

                "release":
                    platform.release(),

                "version":
                    platform.version(),

                "architecture":
                    platform.machine()
            },

            "cpu": {

                "name":
                    cpu.get(
                        "Name"
                    )
                    or
                    platform.processor()
                    or
                    "",

                "cores":
                    cpu.get(
                        "NumberOfCores"
                    ),

                "logical_processors":
                    cpu.get(
                        "NumberOfLogicalProcessors"
                    ),

                "max_clock_mhz":
                    cpu.get(
                        "MaxClockSpeed"
                    )
            },

            "ram": {

                "total_gb":
                    round(
                        memory.total
                        /
                        (1024 ** 3),
                        1
                    )
            },

            "gpus":
                gpu,

            "bios":
                bios,

            "battery":
                battery,

            "disks":
                disks,

            "folders":
                folders
        }


        self._save_cache()


        print(
            "[DEVICE] Perfil concluído."
        )


        return self.profile


    # =========================================================
    # DADOS DINÂMICOS
    # =========================================================

    def refresh_dynamic(
        self
    ):

        memory = (
            psutil
            .virtual_memory()
        )


        dynamic = {

            "cpu_percent":
                round(
                    psutil.cpu_percent(
                        interval=0.08
                    ),
                    1
                ),

            "ram_percent":
                round(
                    float(
                        memory.percent
                    ),
                    1
                ),

            "ram_available_gb":
                round(
                    memory.available
                    /
                    (1024 ** 3),
                    1
                )
        }


        try:

            battery = (
                psutil
                .sensors_battery()
            )


            if battery:

                dynamic[
                    "battery_percent"
                ] = round(
                    float(
                        battery.percent
                    ),
                    1
                )


                dynamic[
                    "battery_plugged"
                ] = bool(
                    battery.power_plugged
                )


        except Exception:

            pass


        return dynamic


    # =========================================================
    # FOLDER
    # =========================================================

    def get_folder(
        self,
        name
    ):

        return (

            self.profile
            .get(
                "folders",
                {}
            )
            .get(
                str(
                    name
                ).lower()
            )
        )


    # =========================================================
    # CONTEXTO PARA IA
    # =========================================================

    def compact_context(
        self
    ):

        p = self.profile

        dynamic = (
            self.refresh_dynamic()
        )


        gpu_names = []


        for gpu in p.get(
            "gpus",
            []
        ):

            if (

                isinstance(
                    gpu,
                    dict
                )

                and

                gpu.get(
                    "Name"
                )

            ):

                gpu_names.append(
                    str(
                        gpu[
                            "Name"
                        ]
                    )
                )


        disk_parts = []


        for disk in p.get(
            "disks",
            []
        )[:4]:

            disk_parts.append(

                f"{disk.get('mountpoint')} "
                f"{disk.get('free_gb')}GB livres/"
                f"{disk.get('total_gb')}GB"
            )


        device_name = " ".join(

            item

            for item in [

                p.get(
                    "manufacturer",
                    ""
                ),

                p.get(
                    "model",
                    ""
                )
            ]

            if item
        ).strip()


        parts = [

            (
                "Notebook: "
                +
                (
                    device_name
                    or
                    "Windows 11 PC"
                )
            ),

            (
                "CPU: "
                +
                str(
                    p
                    .get(
                        "cpu",
                        {}
                    )
                    .get(
                        "name",
                        ""
                    )
                )
            ),

            (
                f"RAM: "
                f"{p.get('ram', {}).get('total_gb', '?')}GB; "
                f"uso "
                f"{dynamic.get('ram_percent', '?')}%"
            ),

            (
                "GPU: "
                +
                (
                    ", ".join(
                        gpu_names
                    )

                    if gpu_names

                    else
                    "não identificada"
                )
            ),

            (
                "Windows: "
                f"{p.get('os', {}).get('release', '')} "
                f"{p.get('os', {}).get('architecture', '')}"
            ),

            (
                "Discos: "
                +
                (
                    "; ".join(
                        disk_parts
                    )

                    if disk_parts

                    else
                    "não identificados"
                )
            )
        ]


        if (
            "battery_percent"
            in
            dynamic
        ):

            state = (

                "na tomada"

                if dynamic.get(
                    "battery_plugged"
                )

                else
                "na bateria"
            )


            parts.append(

                f"Bateria: "
                f"{dynamic['battery_percent']}% "
                f"({state})"
            )


        return " | ".join(
            parts
        )


    # =========================================================
    # RESUMO COMPLETO
    # =========================================================

    def detailed_summary(
        self
    ):

        p = self.profile

        dynamic = (
            self.refresh_dynamic()
        )


        gpu_names = [

            gpu.get(
                "Name"
            )

            for gpu in p.get(
                "gpus",
                []
            )

            if (

                isinstance(
                    gpu,
                    dict
                )

                and

                gpu.get(
                    "Name"
                )
            )
        ]


        return {

            "manufacturer":
                p.get(
                    "manufacturer"
                ),

            "model":
                p.get(
                    "model"
                ),

            "cpu":
                p.get(
                    "cpu"
                ),

            "ram_total_gb":
                p
                .get(
                    "ram",
                    {}
                )
                .get(
                    "total_gb"
                ),

            "ram_percent":
                dynamic.get(
                    "ram_percent"
                ),

            "cpu_percent":
                dynamic.get(
                    "cpu_percent"
                ),

            "gpus":
                gpu_names,

            "battery_percent":
                dynamic.get(
                    "battery_percent"
                ),

            "battery_plugged":
                dynamic.get(
                    "battery_plugged"
                ),

            "disks":
                p.get(
                    "disks",
                    []
                ),

            "folders":
                p.get(
                    "folders",
                    {}
                ),

            "os":
                p.get(
                    "os",
                    {}
                )
        }