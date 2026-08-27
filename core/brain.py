import json
import threading
import time

import requests

from config import (
    CONVERSATION_MEMORY_MESSAGES,
    FALLBACK_MODEL,
    MAX_APPS_IN_CONTEXT,
    MAX_RESPONSE_CHARS,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_TAGS_URL,
    OLLAMA_TIMEOUT,
    OLLAMA_URL,
    PRIMARY_MODEL,
    ROUTER_CONTEXT_SIZE,
    ROUTER_MAX_TOKENS,
    ROUTER_TEMPERATURE
)

from core.memory import ConversationMemory


class JarvisBrain:

    ACTIONS = [

        "open_app",

        "open_site",

        "open_folder",

        "open_settings",

        "search_web",

        "search_youtube",

        "volume_up",

        "volume_down",

        "volume_mute",

        "media_play_pause",

        "media_next",

        "media_previous",

        "system_info",

        "refresh_inventory",

        "chat",

        "none"
    ]


    # =========================================================
    # JSON SCHEMA
    # =========================================================

    RESPONSE_SCHEMA = {

        "type":
            "object",

        "properties": {

            "action": {

                "type":
                    "string",

                "enum":
                    ACTIONS
            },

            "target": {

                "type":
                    "string"
            },

            "query": {

                "type":
                    "string"
            },

            "amount": {

                "type":
                    "integer",

                "minimum":
                    0,

                "maximum":
                    20
            },

            "reply": {

                "type":
                    "string"
            }
        },

        "required": [

            "action",

            "target",

            "query",

            "amount",

            "reply"
        ]
    }


    # =========================================================
    # INIT
    # =========================================================

    def __init__(
        self,
        scanner=None,
        app_finder=None,
        auto_warmup=True
    ):

        self.scanner = scanner

        self.app_finder = app_finder


        self.session = (
            requests.Session()
        )


        self.memory = ConversationMemory(

            CONVERSATION_MEMORY_MESSAGES
        )


        self.model = (
            self._select_model()
        )


        self.available = False

        self.last_duration = 0.0


        if auto_warmup:

            threading.Thread(

                target=self.warmup,

                daemon=True

            ).start()


    # =========================================================
    # MODELOS INSTALADOS
    # =========================================================

    def _installed_model_names(
        self
    ):

        try:

            response = (
                self.session
                .get(
                    OLLAMA_TAGS_URL,
                    timeout=5
                )
            )


            response.raise_for_status()


            data = response.json()


            names = set()


            for item in data.get(
                "models",
                []
            ):

                name = (

                    item.get(
                        "name"
                    )

                    or

                    item.get(
                        "model"
                    )
                )


                if name:

                    names.add(
                        str(
                            name
                        )
                    )


            return names


        except Exception:

            return set()


    # =========================================================
    # ESCOLHER MODELO
    # =========================================================

    def _select_model(
        self
    ):

        names = (
            self._installed_model_names()
        )


        if PRIMARY_MODEL in names:

            return PRIMARY_MODEL


        if FALLBACK_MODEL in names:

            return FALLBACK_MODEL


        return PRIMARY_MODEL


    # =========================================================
    # APPS
    # =========================================================

    def _apps_context(
        self
    ):

        if self.app_finder is None:

            return ""


        try:

            names = (
                self.app_finder
                .names(
                    MAX_APPS_IN_CONTEXT
                )
            )


            return ", ".join(
                names
            )


        except Exception:

            return ""


    # =========================================================
    # DEVICE
    # =========================================================

    def _device_context(
        self
    ):

        if self.scanner is None:

            return "Windows 11."


        try:

            return (
                self.scanner
                .compact_context()
            )


        except Exception:

            return "Windows 11."


    # =========================================================
    # SYSTEM PROMPT
    # =========================================================

    def _system_prompt(
        self
    ):

        apps = (
            self._apps_context()
        )


        device = (
            self._device_context()
        )


        return f"""
Você é o cérebro local do JARVIS em um notebook Windows 11.

Entenda português brasileiro natural, informal, com sinônimos e contexto.

Não exija frases exatas.
Descubra a intenção real.

Notebook real:
{device}

Aplicativos detectados:
{apps}

Ações:

open_app = abrir programa instalado.
open_site = abrir site.
open_folder = abrir pasta conhecida.
open_settings = Configurações do Windows.
search_web = pesquisar na web.
search_youtube = pesquisar no YouTube.
volume_up/down/mute = controlar áudio.
media_play_pause/next/previous = controlar mídia.

system_info = informação REAL do notebook.

Targets úteis de system_info:
device
cpu
ram
gpu
disk
battery
os
apps

refresh_inventory = reexaminar hardware e aplicativos.

chat = conversar ou responder pergunta geral.

none = pedido sem informação suficiente.

Regras:

Para conversa, escreva resposta curta e natural em reply.

Para ação, target/query devem conter apenas o necessário.

Se o usuário disser algo indireto como "quero programar",
use os aplicativos detectados para inferir o programa provável.

Use contexto recente.

Nunca invente hardware, aplicativos ou informações do notebook.

Nunca gere comandos arbitrários de terminal,
PowerShell, scripts ou operações destrutivas.

Responda somente conforme o schema JSON.
""".strip()


    # =========================================================
    # WARMUP
    # =========================================================

    def warmup(
        self
    ):

        self.model = (
            self._select_model()
        )


        payload = {

            "model":
                self.model,

            "messages": [

                {

                    "role":
                        "user",

                    "content":
                        "Responda apenas OK."
                }
            ],

            "stream":
                False,

            "keep_alive":
                OLLAMA_KEEP_ALIVE,

            "options": {

                "temperature":
                    0,

                "num_predict":
                    4,

                "num_ctx":
                    512
            }
        }


        # Qwen3 pensa por padrão.
        # Não precisamos disso para roteamento.

        if self.model.startswith(
            "qwen3"
        ):

            payload[
                "think"
            ] = False


        try:

            response = (
                self.session
                .post(

                    OLLAMA_URL,

                    json=payload,

                    timeout=90
                )
            )


            self.available = bool(
                response.ok
            )


            if response.ok:

                print(

                    f"[BRAIN] "
                    f"{self.model} "
                    f"carregado na memória."
                )


            else:

                print(

                    f"[BRAIN] "
                    f"Ollama HTTP "
                    f"{response.status_code}"
                )


        except Exception as error:

            self.available = False


            print(

                f"[BRAIN] "
                f"Warmup falhou: "
                f"{error}"
            )


        return self.available


    # =========================================================
    # UNDERSTAND
    # =========================================================

    def understand(
        self,
        user_text
    ):

        if not user_text:

            return {

                "action":
                    "none",

                "target":
                    "",

                "query":
                    "",

                "amount":
                    0,

                "reply":
                    ""
            }


        messages = [

            {

                "role":
                    "system",

                "content":
                    self._system_prompt()
            }
        ]


        messages.extend(
            self.memory.get_messages()
        )


        messages.append(
            {

                "role":
                    "user",

                "content":
                    str(
                        user_text
                    )
            }
        )


        payload = {

            "model":
                self.model,

            "messages":
                messages,

            "stream":
                False,

            "format":
                self.RESPONSE_SCHEMA,

            "keep_alive":
                OLLAMA_KEEP_ALIVE,

            "options": {

                "temperature":
                    ROUTER_TEMPERATURE,

                "num_predict":
                    ROUTER_MAX_TOKENS,

                "num_ctx":
                    ROUTER_CONTEXT_SIZE
            }
        }


        if self.model.startswith(
            "qwen3"
        ):

            payload[
                "think"
            ] = False


        started = (
            time.perf_counter()
        )


        try:

            response = (
                self.session
                .post(

                    OLLAMA_URL,

                    json=payload,

                    timeout=
                        OLLAMA_TIMEOUT
                )
            )


            response.raise_for_status()


            self.available = True


            self.last_duration = (

                time.perf_counter()

                -

                started
            )


            data = (
                response.json()
            )


            content = (

                data
                .get(
                    "message",
                    {}
                )
                .get(
                    "content",
                    ""
                )
            )


            decision = json.loads(
                content
            )


            decision = (
                self._validate(
                    decision
                )
            )


            print(

                f"[BRAIN] "
                f"{self.model} -> "
                f"{decision['action']} "
                f"em "
                f"{self.last_duration:.2f}s"
            )


            return decision


        except Exception as error:

            self.last_duration = (

                time.perf_counter()

                -

                started
            )


            print(
                f"[BRAIN] Falha: {error}"
            )


            return {

                "action":
                    "chat",

                "target":
                    "",

                "query":
                    "",

                "amount":
                    0,

                "reply":
                    (
                        "Meu modelo local não respondeu direito. "
                        "Tente de novo em um instante."
                    )
            }


    # =========================================================
    # VALIDATE
    # =========================================================

    def _validate(
        self,
        decision
    ):

        if not isinstance(
            decision,
            dict
        ):

            decision = {}


        action = str(

            decision.get(
                "action",
                "none"
            )

        ).strip()


        if action not in self.ACTIONS:

            action = "none"


        try:

            amount = int(

                decision.get(
                    "amount",
                    0
                )
            )


        except Exception:

            amount = 0


        reply = str(

            decision.get(
                "reply",
                ""
            )

        ).strip()[

            :MAX_RESPONSE_CHARS
        ]


        return {

            "action":
                action,

            "target":
                str(
                    decision.get(
                        "target",
                        ""
                    )
                ).strip(),

            "query":
                str(
                    decision.get(
                        "query",
                        ""
                    )
                ).strip(),

            "amount":
                max(
                    0,
                    min(
                        amount,
                        20
                    )
                ),

            "reply":
                reply
        }


    # =========================================================
    # MEMORY
    # =========================================================

    def remember(
        self,
        user_text,
        assistant_text
    ):

        self.memory.add_user(
            user_text
        )


        if assistant_text:

            self.memory.add_assistant(
                assistant_text
            )


    def clear_memory(
        self
    ):

        self.memory.clear()