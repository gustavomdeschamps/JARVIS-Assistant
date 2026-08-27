import os
import random

from core.app_finder import AppFinder

from core.brain import JarvisBrain

from core.system_scanner import SystemScanner

from core.windows_controller import WindowsController


class CommandSystem:

    def __init__(
        self,
        voice,
        scanner=None,
        app_finder=None,
        brain=None
    ):

        self.voice = voice


        self.scanner = (

            scanner

            or

            SystemScanner()
        )


        self.app_finder = (

            app_finder

            or

            AppFinder()
        )


        self.windows = (
            WindowsController(
                self.app_finder
            )
        )


        self.brain = (

            brain

            or

            JarvisBrain(

                self.scanner,

                self.app_finder
            )
        )


    # =========================================================
    # RESPONSE
    # =========================================================

    def respond(
        self,
        text
    ):

        if text:

            self.voice.speak(
                text
            )


        return {

            "text":
                text,

            "exit":
                False
        }


    # =========================================================
    # SYSTEM INFO
    # =========================================================

    def _system_info(
        self,
        target
    ):

        target = str(
            target
            or
            "device"
        ).lower().strip()


        data = (
            self.scanner
            .detailed_summary()
        )


        # =====================================================
        # NOTEBOOK
        # =====================================================

        if target in [

            "device",
            "notebook",
            "pc",
            "computer",
            "computador"

        ]:

            maker = (
                data.get(
                    "manufacturer"
                )
                or
                ""
            )


            model = (
                data.get(
                    "model"
                )
                or
                ""
            )


            cpu = (

                data
                .get(
                    "cpu",
                    {}
                )
                .get(
                    "name"
                )

                or

                "processador não identificado"
            )


            ram = data.get(
                "ram_total_gb"
            )


            gpu = (

                ", ".join(
                    data.get(
                        "gpus"
                    )
                    or
                    []
                )

                or

                "GPU não identificada"
            )


            return (

                f"Este notebook é "
                f"{maker} {model}. "
                f"Tem {cpu}, "
                f"{ram} gigabytes de RAM "
                f"e {gpu}."
            )


        # =====================================================
        # RAM
        # =====================================================

        if target in [

            "ram",
            "memoria",
            "memória"

        ]:

            return (

                f"Você tem "
                f"{data.get('ram_total_gb')} "
                f"gigabytes de RAM "
                f"e o uso atual está em "
                f"{data.get('ram_percent')} "
                f"por cento."
            )


        # =====================================================
        # CPU
        # =====================================================

        if target in [

            "cpu",
            "processador"

        ]:

            cpu = (
                data.get(
                    "cpu",
                    {}
                )
            )


            return (

                f"O processador é "
                f"{cpu.get('name')}. "
                f"O uso atual está em "
                f"{data.get('cpu_percent')} "
                f"por cento."
            )


        # =====================================================
        # GPU
        # =====================================================

        if target in [

            "gpu",

            "video",

            "vídeo",

            "placa de video",

            "placa de vídeo"

        ]:

            gpus = (
                data.get(
                    "gpus"
                )
                or
                []
            )


            if not gpus:

                return (
                    "Não consegui identificar "
                    "a GPU deste notebook."
                )


            return (

                "As GPUs identificadas são: "

                +

                ", ".join(
                    gpus
                )

                +

                "."
            )


        # =====================================================
        # BATERIA
        # =====================================================

        if target in [

            "battery",
            "bateria"

        ]:

            percent = data.get(
                "battery_percent"
            )


            if percent is None:

                return (

                    "O Windows não forneceu "
                    "informações de bateria."
                )


            state = (

                "e está ligado na tomada"

                if data.get(
                    "battery_plugged"
                )

                else
                "e está usando a bateria"
            )


            return (

                f"A bateria está em "
                f"{percent} por cento "
                f"{state}."
            )


        # =====================================================
        # DISK
        # =====================================================

        if target in [

            "disk",
            "disco",
            "ssd",
            "armazenamento",
            "espaco",
            "espaço"

        ]:

            disks = (
                data.get(
                    "disks"
                )
                or
                []
            )


            if not disks:

                return (
                    "Não consegui ler "
                    "os discos do computador."
                )


            parts = []


            for disk in disks[:3]:

                parts.append(

                    f"{disk.get('mountpoint')} "
                    f"com "
                    f"{disk.get('free_gb')} "
                    f"gigabytes livres "
                    f"de "
                    f"{disk.get('total_gb')}"
                )


            return (

                "Armazenamento: "

                +

                "; ".join(
                    parts
                )

                +

                "."
            )


        # =====================================================
        # WINDOWS
        # =====================================================

        if target in [

            "os",
            "windows",
            "sistema"

        ]:

            os_data = (
                data.get(
                    "os",
                    {}
                )
            )


            return (

                f"O sistema é "
                f"{os_data.get('name')} "
                f"{os_data.get('release')} "
                f"em arquitetura "
                f"{os_data.get('architecture')}."
            )


        # =====================================================
        # APPS
        # =====================================================

        if target in [

            "apps",
            "aplicativos",
            "programas"

        ]:

            names = (
                self.app_finder
                .names(
                    18
                )
            )


            return (

                f"Eu tenho "
                f"{len(self.app_finder.apps)} "
                f"entradas de aplicativos indexadas. "
                f"Alguns deles são: "
                f"{', '.join(names)}."
            )


        return (

            "Não identifiquei "
            "qual informação do notebook você quer."
        )


    # =========================================================
    # EXECUTE
    # =========================================================

    def execute(
        self,
        user_text
    ):

        decision = (
            self.brain
            .understand(
                user_text
            )
        )


        action = decision[
            "action"
        ]


        target = decision[
            "target"
        ]


        query = decision[
            "query"
        ]


        amount = decision[
            "amount"
        ]


        reply = decision[
            "reply"
        ]


        final = ""


        # =====================================================
        # CHAT
        # =====================================================

        if action == "chat":

            final = (

                reply

                or

                "Estou ouvindo."
            )


        # =====================================================
        # APP
        # =====================================================

        elif action == "open_app":

            success = (
                self.windows
                .open_app(
                    target
                )
            )


            final = (

                reply

                or

                (
                    random.choice(
                        [
                            "Pronto.",
                            "Feito.",
                            "Já abri."
                        ]
                    )

                    if success

                    else

                    f"Não encontrei "
                    f"{target} "
                    f"neste notebook."
                )
            )


        # =====================================================
        # SITE
        # =====================================================

        elif action == "open_site":

            success = (
                self.windows
                .open_site(
                    target
                )
            )


            if success:

                final = (

                    reply
                    or
                    "Pronto."
                )


            else:

                self.windows.search_web(
                    target
                )


                final = (

                    f"Não achei um endereço direto "
                    f"para {target}, "
                    f"então pesquisei para você."
                )


        # =====================================================
        # FOLDER
        # =====================================================

        elif action == "open_folder":

            path = (
                self.scanner
                .get_folder(
                    target
                )
            )


            if path:

                try:

                    os.startfile(
                        path
                    )


                    success = True


                except Exception:

                    success = False


            else:

                success = (
                    self.windows
                    .open_folder(
                        target
                    )
                )


            final = (

                reply

                or

                (
                    "Pronto."

                    if success

                    else

                    f"Não encontrei "
                    f"a pasta {target}."
                )
            )


        # =====================================================
        # SETTINGS
        # =====================================================

        elif action == "open_settings":

            final = (

                "Pronto."

                if (
                    self.windows
                    .open_settings()
                )

                else

                "Não consegui abrir as configurações."
            )


        # =====================================================
        # WEB
        # =====================================================

        elif action == "search_web":

            success = (
                self.windows
                .search_web(
                    query
                    or
                    target
                )
            )


            final = (

                reply

                or

                (
                    "Pesquisando."

                    if success

                    else

                    "Não identifiquei o que pesquisar."
                )
            )


        # =====================================================
        # YOUTUBE
        # =====================================================

        elif action == "search_youtube":

            success = (
                self.windows
                .search_youtube(
                    query
                    or
                    target
                )
            )


            final = (

                reply

                or

                (
                    "Procurando no YouTube."

                    if success

                    else

                    "Não identifiquei o que procurar."
                )
            )


        # =====================================================
        # VOLUME
        # =====================================================

        elif action == "volume_up":

            self.windows.volume_up(
                amount
                or
                4
            )


            final = (
                reply
                or
                "Pronto."
            )


        elif action == "volume_down":

            self.windows.volume_down(
                amount
                or
                4
            )


            final = (
                reply
                or
                "Pronto."
            )


        elif action == "volume_mute":

            if hasattr(
                self.windows,
                "volume_mute"
            ):

                self.windows.volume_mute()


            else:

                self.windows.mute()


            final = (
                reply
                or
                "Pronto."
            )


        # =====================================================
        # MEDIA
        # =====================================================

        elif action == "media_play_pause":

            self.windows.media_play_pause()

            final = (
                reply
                or
                "Pronto."
            )


        elif action == "media_next":

            self.windows.media_next()

            final = (
                reply
                or
                "Pronto."
            )


        elif action == "media_previous":

            self.windows.media_previous()

            final = (
                reply
                or
                "Pronto."
            )


        # =====================================================
        # SYSTEM INFO
        # =====================================================

        elif action == "system_info":

            final = (
                self._system_info(
                    target
                )
            )


        # =====================================================
        # REFRESH INVENTORY
        # =====================================================

        elif action == "refresh_inventory":

            self.scanner.scan(
                force=True
            )


            total = (
                self.app_finder
                .rebuild_index()
            )


            final = (

                f"Atualizei o inventário do notebook "
                f"e indexei "
                f"{total} "
                f"entradas de aplicativos."
            )


        # =====================================================
        # NONE
        # =====================================================

        else:

            final = (

                reply

                or

                (
                    "Entendi sua fala, "
                    "mas não tenho uma ação segura "
                    "para esse pedido."
                )
            )


        # =====================================================
        # MEMORY
        # =====================================================

        self.brain.remember(
            user_text,
            final
        )


        return self.respond(
            final
        )