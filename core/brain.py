"""JarvisBrain: turns free-form Portuguese speech into a structured action.

The brain talks to a locally-running Ollama model and asks it to return
JSON matching ``RESPONSE_SCHEMA`` (Ollama enforces this via its
"structured output" `format` parameter). It knows nothing about how to
*execute* an action — that is ``core/commands.py``'s job — it only decides
*what* the user wants, using:

- the device's real hardware profile (``SystemScanner``),
- the apps actually installed on this machine (``AppFinder``),
- long-term facts remembered about the user (``LongTermMemory``),
- and the recent conversation (``ConversationMemory``).

Compared to the original version this brain is meaningfully hardened:

- Requests to Ollama are retried with exponential backoff instead of
  failing on the first hiccup (Ollama loading a model into RAM for the
  first time can legitimately take a few seconds).
- If the model returns malformed JSON (small local models occasionally
  wrap it in prose or truncate it), a best-effort repair pass tries to
  pull out the first balanced ``{...}`` block before giving up.
- A much larger, safety-conscious action vocabulary: system power actions,
  a calculator, a unit converter, timers/reminders, notes, weather, and
  long-term memory of facts about the user.
"""

import json
import re
import threading
import time

import requests

from config import (
    BRAIN_MAX_RETRIES,
    BRAIN_RETRY_BACKOFF_SECONDS,
    CONVERSATION_MEMORY_MESSAGES,
    FACTS_FILE,
    FALLBACK_MODEL,
    MAX_APPS_IN_CONTEXT,
    MAX_LONG_TERM_FACTS,
    MAX_RESPONSE_CHARS,
    MEMORY_SUMMARY_TRIGGER,
    OLLAMA_KEEP_ALIVE,
    OLLAMA_TAGS_URL,
    OLLAMA_TIMEOUT,
    OLLAMA_URL,
    PRIMARY_MODEL,
    ROUTER_CONTEXT_SIZE,
    ROUTER_MAX_TOKENS,
    ROUTER_TEMPERATURE,
)
from core.logger import get_logger
from core.memory import ConversationMemory, LongTermMemory

logger = get_logger(__name__)


class JarvisBrain:

    # Every action the LLM router is allowed to choose. Keeping this as a
    # flat enum (rather than free-form text) is what lets a small 1.7B
    # model stay reliable: it never has to invent syntax, it just picks
    # one label and fills in a few generic fields.
    ACTIONS = [
        "open_app",
        "close_app",
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
        "system_power",
        "set_brightness",
        "take_screenshot",
        "refresh_inventory",
        "calculate",
        "convert_units",
        "get_weather",
        "add_note",
        "list_notes",
        "delete_note",
        "set_timer",
        "list_timers",
        "cancel_timer",
        "set_reminder",
        "list_reminders",
        "cancel_reminder",
        "remember_fact",
        "recall_fact",
        "forget_fact",
        "tell_time",
        "tell_date",
        "clear_memory",
        "repeat_last",
        "help",
        "chat",
        "none",
    ]

    # =========================================================
    # JSON SCHEMA (enforced by Ollama's structured-output mode)
    # =========================================================

    RESPONSE_SCHEMA = {
        "type": "object",
        "properties": {
            "action": {"type": "string", "enum": ACTIONS},
            "target": {"type": "string"},
            "query": {"type": "string"},
            "amount": {"type": "integer", "minimum": 0, "maximum": 500},
            "reply": {"type": "string"},
        },
        "required": ["action", "target", "query", "amount", "reply"],
    }

    _EMPTY_DECISION = {
        "action": "none",
        "target": "",
        "query": "",
        "amount": 0,
        "reply": "",
    }

    # =========================================================
    # INIT
    # =========================================================

    def __init__(self, scanner=None, app_finder=None, auto_warmup=True):
        self.scanner = scanner
        self.app_finder = app_finder

        self.session = requests.Session()

        self.memory = ConversationMemory(
            CONVERSATION_MEMORY_MESSAGES,
            summary_trigger=MEMORY_SUMMARY_TRIGGER,
        )

        self.long_term = LongTermMemory(FACTS_FILE, max_facts=MAX_LONG_TERM_FACTS)

        self.model = self._select_model()

        self.available = False
        self.last_duration = 0.0
        self.last_response_text = ""

        if auto_warmup:
            threading.Thread(target=self.warmup, daemon=True).start()

    # =========================================================
    # MODELOS INSTALADOS
    # =========================================================

    def _installed_model_names(self):
        try:
            response = self.session.get(OLLAMA_TAGS_URL, timeout=5)
            response.raise_for_status()
            data = response.json()

            names = set()
            for item in data.get("models", []):
                name = item.get("name") or item.get("model")
                if name:
                    names.add(str(name))

            return names

        except Exception as error:
            logger.debug("Não foi possível listar modelos do Ollama: %s", error)
            return set()

    # =========================================================
    # ESCOLHER MODELO
    # =========================================================

    def _select_model(self):
        names = self._installed_model_names()

        if PRIMARY_MODEL in names:
            return PRIMARY_MODEL

        if FALLBACK_MODEL in names:
            logger.warning(
                "Modelo primário '%s' não encontrado, usando fallback '%s'.",
                PRIMARY_MODEL,
                FALLBACK_MODEL,
            )
            return FALLBACK_MODEL

        if names:
            logger.warning(
                "Nem o modelo primário nem o fallback estão instalados no "
                "Ollama. Tentando '%s' mesmo assim — rode "
                "'ollama pull %s' para corrigir.",
                PRIMARY_MODEL,
                PRIMARY_MODEL,
            )

        return PRIMARY_MODEL

    # =========================================================
    # CONTEXTO: APPS / DISPOSITIVO / FATOS
    # =========================================================

    def _apps_context(self):
        if self.app_finder is None:
            return ""

        try:
            return ", ".join(self.app_finder.names(MAX_APPS_IN_CONTEXT))
        except Exception as error:
            logger.debug("Falha ao montar contexto de apps: %s", error)
            return ""

    def _device_context(self):
        if self.scanner is None:
            return "Windows 11."

        try:
            return self.scanner.compact_context()
        except Exception as error:
            logger.debug("Falha ao montar contexto do dispositivo: %s", error)
            return "Windows 11."

    def _facts_context(self):
        try:
            return self.long_term.as_context_string()
        except Exception as error:
            logger.debug("Falha ao montar contexto de fatos: %s", error)
            return ""

    # =========================================================
    # SYSTEM PROMPT
    # =========================================================

    def _system_prompt(self):
        apps = self._apps_context()
        device = self._device_context()
        facts = self._facts_context()
        summary = self.memory.get_summary()

        facts_block = facts or "Nenhum fato conhecido ainda sobre o usuário."
        summary_block = summary or "Nenhum resumo anterior."

        return f"""
Você é o cérebro local do JARVIS em um notebook Windows 11.

Entenda português brasileiro natural, informal, com sinônimos e contexto.
Não exija frases exatas. Descubra a intenção real por trás do pedido.

Notebook real:
{device}

Aplicativos detectados:
{apps}

Fatos conhecidos sobre o usuário:
{facts_block}

Resumo da conversa mais antiga (contexto, não repita literalmente):
{summary_block}

=== AÇÕES DISPONÍVEIS ===

open_app / close_app = abrir ou fechar um programa instalado (target = nome do programa).
open_site = abrir um site (target = nome ou domínio do site).
open_folder = abrir uma pasta conhecida (Downloads, Documentos, Desktop, ...).
open_settings = abrir as Configurações do Windows.
search_web = pesquisar algo na web (query = o que pesquisar).
search_youtube = pesquisar algo no YouTube (query = o que procurar).
volume_up / volume_down = ajustar volume (amount = passos, padrão 4).
volume_mute = silenciar/dessilenciar o volume.
media_play_pause / media_next / media_previous = controlar mídia em reprodução.

system_info = informação REAL do notebook. target ∈
    device, cpu, ram, gpu, disk, battery, os, apps.
system_power = ação de energia no PC. target ∈ lock, sleep, shutdown, restart.
    Use lock para "trave o pc"/"bloqueie a tela".
    Use sleep para "coloque para dormir"/"modo de suspensão".
    Use shutdown para "desligue o computador".
    Use restart para "reinicie o computador".
set_brightness = ajustar o brilho da tela (amount = 0 a 100).
take_screenshot = capturar a tela atual.
refresh_inventory = reexaminar hardware e aplicativos instalados.

calculate = fazer uma conta matemática (query = a expressão, ex: "15 vezes 3").
convert_units = converter unidades (query = ex: "10 quilômetros em milhas").
get_weather = previsão do tempo (target = cidade, vazio = localização atual).

add_note = guardar uma anotação rápida (query = o texto da nota).
list_notes = listar as últimas anotações (amount = quantas, padrão 5).
delete_note = apagar uma anotação (amount = id da nota, ou target="ultima").

set_timer = criar um temporizador (amount = minutos, query = rótulo opcional).
list_timers = listar temporizadores ativos.
cancel_timer = cancelar temporizador(es) (amount = id, ou target="todos").

set_reminder = criar um lembrete futuro (amount = minutos, query = o que lembrar).
list_reminders = listar lembretes pendentes.
cancel_reminder = cancelar lembrete(s) (amount = id, ou target="todos").

remember_fact = guardar um fato permanente sobre o usuário
    (target = chave curta, ex: "nome"; query = o valor, ex: "Gustavo").
recall_fact = relembrar um fato guardado (target = chave).
forget_fact = esquecer um fato (target = chave, ou target="tudo").

tell_time = dizer as horas agora.
tell_date = dizer a data de hoje.
clear_memory = esquecer o histórico recente da conversa.
repeat_last = repetir a última resposta falada.
help = explicar o que o JARVIS sabe fazer.

chat = conversar ou responder uma pergunta geral que não é uma das ações acima.
none = pedido sem informação suficiente para agir.

=== EXEMPLOS ===

"abre o spotify" -> open_app, target="spotify"
"fecha o chrome" -> close_app, target="chrome"
"quanto é 12 vezes 8" -> calculate, query="12 vezes 8"
"converte 5 km em milhas" -> convert_units, query="5 km em milhas"
"anota que preciso ligar pro dentista" -> add_note, query="ligar pro dentista"
"toca um timer de 10 minutos" -> set_timer, amount=10
"me lembra em 20 minutos de tirar o bolo do forno" -> set_reminder, amount=20, query="tirar o bolo do forno"
"meu nome é Gustavo" -> remember_fact, target="nome", query="Gustavo"
"qual é o meu nome" -> recall_fact, target="nome"
"que horas são" -> tell_time
"desliga o computador" -> system_power, target="shutdown"
"trava a tela" -> system_power, target="lock"
"o que você sabe fazer" -> help

=== REGRAS ===

Para conversa (chat), escreva uma resposta curta e natural em reply.
Para ação, target/query devem conter apenas o necessário, sem enfeites.

Se o usuário disser algo indireto como "quero programar",
use os aplicativos detectados para inferir o programa provável.

Use o contexto recente e o resumo da conversa quando fizer sentido.

Nunca invente hardware, aplicativos ou informações do notebook.
Nunca invente fatos sobre o usuário que não estão na lista acima.

Nunca gere comandos arbitrários de terminal, PowerShell, scripts,
ou qualquer operação fora da lista de ações acima.

Responda somente conforme o schema JSON.
""".strip()

    # =========================================================
    # CHAMADA HTTP AO OLLAMA (com retry)
    # =========================================================

    def _post_with_retry(self, payload, timeout):
        last_error = None

        for attempt in range(BRAIN_MAX_RETRIES + 1):
            try:
                response = self.session.post(OLLAMA_URL, json=payload, timeout=timeout)
                response.raise_for_status()
                return response

            except Exception as error:
                last_error = error

                if attempt < BRAIN_MAX_RETRIES:
                    delay = BRAIN_RETRY_BACKOFF_SECONDS * (2**attempt)
                    logger.debug(
                        "Chamada ao Ollama falhou (tentativa %s/%s): %s. "
                        "Tentando de novo em %.1fs.",
                        attempt + 1,
                        BRAIN_MAX_RETRIES + 1,
                        error,
                        delay,
                    )
                    time.sleep(delay)

        raise last_error

    # =========================================================
    # WARMUP
    # =========================================================

    def warmup(self):
        self.model = self._select_model()

        payload = {
            "model": self.model,
            "messages": [{"role": "user", "content": "Responda apenas OK."}],
            "stream": False,
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "options": {"temperature": 0, "num_predict": 4, "num_ctx": 512},
        }

        # Qwen3 pensa por padrão. Não precisamos disso para roteamento.
        if self.model.startswith("qwen3"):
            payload["think"] = False

        try:
            response = self._post_with_retry(payload, timeout=90)
            self.available = bool(response.ok)

            if response.ok:
                logger.info("%s carregado na memória.", self.model)
            else:
                logger.error("Ollama HTTP %s durante o warmup.", response.status_code)

        except Exception as error:
            self.available = False
            logger.error(
                "Warmup falhou: %s. Verifique se o Ollama está rodando "
                "('ollama serve') e se o modelo está instalado "
                "('ollama pull %s').",
                error,
                self.model,
            )

        return self.available

    # =========================================================
    # UNDERSTAND
    # =========================================================

    def understand(self, user_text):
        if not user_text:
            return dict(self._EMPTY_DECISION)

        messages = [{"role": "system", "content": self._system_prompt()}]
        messages.extend(self.memory.get_messages())
        messages.append({"role": "user", "content": str(user_text)})

        payload = {
            "model": self.model,
            "messages": messages,
            "stream": False,
            "format": self.RESPONSE_SCHEMA,
            "keep_alive": OLLAMA_KEEP_ALIVE,
            "options": {
                "temperature": ROUTER_TEMPERATURE,
                "num_predict": ROUTER_MAX_TOKENS,
                "num_ctx": ROUTER_CONTEXT_SIZE,
            },
        }

        if self.model.startswith("qwen3"):
            payload["think"] = False

        started = time.perf_counter()

        try:
            response = self._post_with_retry(payload, timeout=OLLAMA_TIMEOUT)
            self.available = True
            self.last_duration = time.perf_counter() - started

            data = response.json()
            content = data.get("message", {}).get("content", "")

            decision = self._parse_decision(content)
            decision = self._validate(decision)

            logger.info(
                "%s -> %s em %.2fs", self.model, decision["action"], self.last_duration
            )

            return decision

        except Exception as error:
            self.last_duration = time.perf_counter() - started
            self.available = False

            logger.error("Falha ao consultar o modelo local: %s", error)

            return {
                "action": "chat",
                "target": "",
                "query": "",
                "amount": 0,
                "reply": (
                    "Meu modelo local não respondeu direito. "
                    "Tente de novo em um instante."
                ),
            }

    # =========================================================
    # PARSE + REPARO DE JSON
    # =========================================================

    def _parse_decision(self, content):
        try:
            return json.loads(content)
        except (json.JSONDecodeError, TypeError):
            pass

        # Pequenos modelos locais às vezes envolvem o JSON em texto extra
        # ou cortam a resposta. Tenta extrair o primeiro bloco {...} e
        # reinterpretar antes de desistir.
        match = re.search(r"\{.*\}", str(content), re.DOTALL)

        if match:
            try:
                repaired = json.loads(match.group(0))
                logger.debug("JSON reparado com sucesso a partir de resposta malformada.")
                return repaired
            except json.JSONDecodeError:
                pass

        logger.warning("Resposta do modelo não era JSON válido: %r", content[:200])
        return {}

    # =========================================================
    # VALIDATE
    # =========================================================

    def _validate(self, decision):
        if not isinstance(decision, dict):
            decision = {}

        action = str(decision.get("action", "none")).strip()
        if action not in self.ACTIONS:
            action = "none"

        try:
            amount = int(decision.get("amount", 0))
        except (TypeError, ValueError):
            amount = 0

        reply = str(decision.get("reply", "")).strip()[:MAX_RESPONSE_CHARS]

        return {
            "action": action,
            "target": str(decision.get("target", "")).strip(),
            "query": str(decision.get("query", "")).strip(),
            "amount": max(0, min(amount, 500)),
            "reply": reply,
        }

    # =========================================================
    # MEMORY
    # =========================================================

    def remember(self, user_text, assistant_text):
        self.memory.add_user(user_text)

        if assistant_text:
            self.memory.add_assistant(assistant_text)
            self.last_response_text = assistant_text

    def clear_memory(self):
        self.memory.clear()

    # =========================================================
    # CAPACIDADES (usado pela ação "help")
    # =========================================================

    def describe_capabilities(self):
        return (
            "Eu abro e fecho programas, abro sites e pastas, pesquiso na "
            "web e no YouTube, controlo volume e mídia, informo dados reais "
            "do notebook, faço contas e conversões de unidade, dou a "
            "previsão do tempo, guardo notas, crio temporizadores e "
            "lembretes, lembro fatos sobre você, e converso normalmente "
            "sobre qualquer assunto. Também sei bloquear, suspender, "
            "desligar e reiniciar o computador, sempre com confirmação "
            "antes de qualquer ação que perca trabalho não salvo."
        )
